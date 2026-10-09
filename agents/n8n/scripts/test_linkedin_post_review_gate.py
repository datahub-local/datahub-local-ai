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
    """The notice must not be the "Error Publishing Post ()" it used to be."""
    text = _nodes(document)["send_error_notification"]["parameters"]["text"]
    assert "select_article_to_post" in text, f"{label}: notice does not name the article"
    assert "$execution.url" not in text, f"{label}: empty $execution.url is still in the notice"
    assert "$json.ERROR" in text, f"{label}: notice does not carry the reason"


@pytest.mark.parametrize("label,document", list(_copies(SHARING)))
def test_nothing_overwrites_the_failure_reason(label, document):
    """set_error_error replaced the sub-workflow's ERROR with the literal "ERROR"."""
    assert "set_error_error" not in _nodes(document), f"{label}: set_error_error is back"
    assert "set_error_error" not in _connections(document), f"{label}: graph still references it"
    assert _targets(_connections(document), "update_status_error") == ["send_error_notification"], (
        f"{label}: update_status_error must reach the notice directly"
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
