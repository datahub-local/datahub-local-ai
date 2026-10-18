"""Guard the LinkedIn post review gate against the failure of 2026-09-30.

Execution 11728 burned five drafts and 3m44s on one article because the gate
rejected every one of them for using the word "harness": the rules banned it as
AI-speak while the drafting rules required naming the technology the article was
about, so no draft could satisfy both. The loop that should have recovered could
not -- it re-rendered an identical prompt, because the only feedback the drafting
prompt carried was the human's, and the gate's own `<explanation>` was discarded
-- and the failure that reached Slack said "Error Publishing Post () in LinkedIn:
ERROR", naming neither the article nor the reason.

These assertions are structural, over the committed exports: the word list lives
in a prompt file that only a model reads, but the loop around it is a graph, and
every property that failed is a property of that graph. The network and the
cluster are not involved.

Both copies of every graph are checked -- the exports carry their nodes twice, at
the top level and inside ``activeVersion``, and a fix applied to one copy is a
live bug.
"""

import json
import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
CREATOR = WORKFLOWS / "linked_in_post_creator.workflow.json"
SHARING = WORKFLOWS / "linked_in_post_sharing.workflow.json"


def _copies(path):
    """Yield (label, document) for both copies of a workflow export."""
    data = json.loads(path.read_text())
    yield "top level", data
    yield "activeVersion", data["activeVersion"]


def _nodes(document):
    return {node["name"]: node for node in document["nodes"]}


def _connections(document):
    return document["connections"]


def _targets(connections, source):
    block = connections.get(source)
    if not block:
        return []
    return [edge["node"] for output in block["main"] for edge in output]


@pytest.mark.parametrize("label,document", list(_copies(CREATOR)))
def test_rejected_draft_is_regenerated_from_the_gate_reason(label, document):
    """The retry edge re-renders the drafting prompt instead of resubmitting it.

    The old edge went straight back to create_post_ai, so every attempt was the
    same prompt sampled again and a rejection for one reason could repeat
    indefinitely.
    """
    connections = _connections(document)
    assert "download_post_prompt" in _targets(connections, "switch_check_rules_llm"), (
        f"{label}: the rejected branch must return through download_post_prompt"
    )

    prompt = _nodes(document)["download_post_prompt"]["parameters"]["workflowInputs"]["value"][
        "template_vars"
    ]
    assert "$json.explanation" in prompt, f"{label}: the rerendered prompt must carry the gate reason"


@pytest.mark.parametrize("label,document", list(_copies(CREATOR)))
def test_gate_explanation_is_extracted(label, document):
    """parse_llm_check_output must keep the reason it used to throw away."""
    js = _nodes(document)["parse_llm_check_output"]["parameters"]["jsCode"]
    assert "<explanation>" in js, f"{label}: explanation not extracted"


@pytest.mark.parametrize("label,document", list(_copies(CREATOR)))
def test_attempt_bound_counts_drafts(label, document):
    """MAX_TRIES must be the number of drafts, not drafts + 2.

    $runIndex is 0 for the first submitted draft, so ``$runIndex > MAX_TRIES``
    spent MAX_TRIES + 2 drafts: MAX_TRIES = 3 produced five attempts.
    """
    rules = _nodes(document)["switch_check_rules_llm"]["parameters"]["rules"]["values"]
    bound = [
        condition["leftValue"]
        for rule in rules
        for condition in rule["conditions"]["conditions"]
        if "MAX_TRIES" in condition.get("rightValue", "")
    ]
    assert bound == ["={{ $runIndex + 1 }}"], f"{label}: unexpected bound expression {bound}"


@pytest.mark.parametrize("label,document", list(_copies(CREATOR)))
def test_gate_failure_reports_its_reason(label, document):
    """The marker alone is not a reason; the explanation travels with it."""
    value = _nodes(document)["set_error_max_tries"]["parameters"]["assignments"]["assignments"][0][
        "value"
    ]
    assert value.startswith("="), f"{label}: ERROR is a literal, so the reason is lost"
    assert "MAX_RETRIES_EXCEEDED" in value and "explanation" in value, (
        f"{label}: ERROR must stay greppable as a gate failure and name a reason"
    )


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_failure_notice_names_the_article_and_the_reason(label, document):
    """The notice must not be the "Error Publishing Post ()" it used to be.

    The failure notice is the error workflow's now, so what it prints is the
    message this path throws -- the reason and the article have to travel in it.
    """
    text = _nodes(document)["stop_and_error"]["parameters"]["errorMessage"]
    assert "select_article_to_post" in text, f"{label}: the reason does not name the article"
    assert "$json.ERROR" in text, f"{label}: the throw does not carry the reason"


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_a_caught_failure_raises_so_n8n_keeps_the_run(label, document):
    """A run that ends "success" is one n8n deletes.

    This workflow saves no successful data (the payload is the published asset),
    so a failure the graph handled itself ended as success: the row was removed,
    the error workflow was never dispatched -- n8n dispatches it only for a run
    that is not a success -- and the "(exec N)" the notice named resolved to
    nothing. Execution 13326 on 2026-10-14 is the case: the row was gone while
    the notice pointed at it. Throwing is what makes the run an error, and an
    error is the one n8n keeps.
    """
    nodes = _nodes(document)
    thrown = nodes["stop_and_error"]
    assert thrown["type"] == "n8n-nodes-base.stopAndError", f"{label}: the failure path does not raise"
    assert not (_connections(document).get("stop_and_error") or {}), (
        f"{label}: the throw is not the end of the branch"
    )
    settings = document.get("settings") or {}
    assert settings.get("saveDataErrorExecution") != "none", (
        f"{label}: a raised failure would be discarded as well"
    )


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_nothing_overwrites_the_failure_reason(label, document):
    """set_error_error replaced the sub-workflow's ERROR with the literal "ERROR"."""
    assert "set_error_error" not in _nodes(document), f"{label}: set_error_error is back"
    assert "set_error_error" not in _connections(document), f"{label}: graph still references it"
    assert _targets(_connections(document), "update_status_error") == ["stop_and_error"], (
        f"{label}: update_status_error must reach the throw directly"
    )

    # The cancelled path sets its own ERROR and still needs the notice.
    assert "send_error_notification" in _targets(_connections(document), "set_error_cancelled"), (
        f"{label}: the cancelled path lost its notice"
    )


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_publish_clears_a_stale_failure_reason(label, document):
    """A publish must not leave an earlier failure's ERROR on the row.

    Found while verifying this change: row 58 read STATUS=PUBLISHED with
    ERROR=MAX_RETRIES_EXCEEDED still on it, because update_status_published_a
    never wrote the column.
    """
    columns = _nodes(document)["update_status_published_a"]["parameters"]["columns"]
    assert columns["value"].get("ERROR") == "", (
        f"{label}: publish does not clear a stale ERROR"
    )
    entry = next(s for s in columns["schema"] if s["id"] == "ERROR")
    assert entry["removed"] is False, f"{label}: ERROR is not writable on the publish node"


PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z_]+)\s*\}\}")
VAR_KEY_RE = re.compile(r'"([A-Z_]+)":')


@pytest.mark.parametrize("label,document", list(_copies(CREATOR)))
def test_the_retry_carries_the_post_the_review_rejected(label, document):
    """The retry edits the post it was told to fix instead of writing a new one.

    The reviewer's reason says "apply these changes", and the drafting prompt carried the reason
    and no post — so the drafter rewrote from nothing. The article lane failed the same way on
    2026-10-18 (executions 14018, 14020), where the retry went looking for material instead of
    editing and the agent's iteration cap ended the run.

    Also holds the prompt's placeholders to the vars the node supplies: a pushed prompt naming one
    DownloadTemplate was not handed stops every run, and this lane had no such guard.
    """
    prompt = (PROMPTS / "linkedin_post.md").read_text(encoding="utf-8")
    declared = {m.group(1) for m in PLACEHOLDER_RE.finditer(prompt)}
    node = _nodes(document)["download_post_prompt"]
    value = node["parameters"]["workflowInputs"]["value"]
    assert value["template_name"] == "prompts/linkedin_post.md", label
    supplied = set(VAR_KEY_RE.findall(value["template_vars"]))
    assert supplied == declared, f"{label}: the prompt and its call disagree on {supplied ^ declared}"
    expr = value["template_vars"]
    assert "$('parse_llm_output').last()" in expr, f"{label}: the retry carries no previous post"
    assert "$('parse_llm_output').item" not in expr, (
        f"{label}: the paired-item lineage runs back through switch_check_rules_llm"
    )
    assert "$('parse_llm_output').first()" not in expr, (
        f"{label}: a third attempt would edit the first post and never converge"
    )
    assert "isExecuted" in expr, f"{label}: an unguarded read throws on the first attempt"


@pytest.mark.parametrize("label,document", list(_copies(CREATOR)))
def test_the_human_retry_falls_back_to_the_post_the_caller_sent(label, document):
    """A human retry is a new invocation, so the post has to arrive on the trigger.

    Same gap as the article lane, found the same day: `parse_llm_output` has not run when the
    human's Retry loops back into `execute_post_creator`, so `PREVIOUS_POST` rendered empty and
    the prompt read that as a first draft. The post is stored nowhere else in this lane —
    `content_queue` has no post column — so the run itself has to carry it.
    """
    value = _nodes(document)["download_post_prompt"]["parameters"]["workflowInputs"]["value"]
    expr = value["template_vars"]
    assert "$('main_trigger').first().json.PREVIOUS_POST" in expr, (
        f"{label}: the caller's post is not the fallback, so a human retry writes from scratch"
    )
    assert expr.index("$('parse_llm_output').isExecuted") < expr.index(
        "$('main_trigger').first().json.PREVIOUS_POST"
    ), f"{label}: the in-run post must win, or an internal retry edits the wrong draft"


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_the_sharing_workflow_passes_the_draft_the_human_rejected(label, document):
    """The post text has no durable home, so it travels in the run.

    `content_queue` carries no post column (URL TITLE STATUS PRIORITY SCORE ORIGIN TOPIC SOURCE
    RATIONALE EXTRA_PROMPT MAX_WORDS PUBLISHED_AT UPDATE_DATE RELEASE_DATE LINKEDIN_URL ENTRY_ID
    ERROR EXECUTION_ID row_number), so the draft the human just read exists only in the run's own
    output — and the call node's earlier run is exactly that: measured with a probe cycle on
    2026-10-18 (execution 14195), a node's `.last()` on its second pass answers the *previous*
    run's value, not the row being built.
    """
    assert "execute_post_creator" in _targets(_connections(document), "switch_user_retry"), (
        f"{label}: the human's Retry no longer re-enters the call node this test is about"
    )
    call = _nodes(document)["execute_post_creator"]["parameters"]["workflowInputs"]
    expr = call["value"]["PREVIOUS_POST"]
    assert "$('execute_post_creator')" in expr, f"{label}: the human retry sends no post"
    assert ".last()" in expr, f"{label}: a third human round would re-send the first post"
    assert "$('execute_post_creator').item" not in expr, (
        f"{label}: a paired-item read through the approval wait"
    )
    assert "isExecuted" in expr, f"{label}: the first pass runs this node too, and would throw"
    assert "PREVIOUS_POST" in [s["id"] for s in call["schema"]], (
        f"{label}: the field is not mapped, so n8n drops it on the way to the sub-workflow"
    )
