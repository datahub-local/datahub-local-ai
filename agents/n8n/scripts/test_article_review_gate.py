"""Guard the article review gate and its retry loop.

`Article Creator` used to hand its first draft straight back: a draft that ran past
`MAX_WORDS`, or that broke a writing rule, came back as `ERROR` and the entry point failed the
whole run (execution 13844 on 2026-10-17 is the case the owner hit -- the draft ran long and
the run ended, having spent the model time and produced nothing). `LinkedIn Post Creator`
already has the shape this needs: a second model pass reviews the draft against the same
committed rules the writer followed, a rejection re-renders the drafting prompt with the
reviewer's own reason, and the loop is bounded so a run that cannot be satisfied reports a
reason instead of spinning.

These assertions are structural, over the committed export, because the loop is a graph and
every property that can silently fail -- the retry edge, the reason travelling into the next
attempt, the bound, the deterministic budget -- is a property of that graph. The network and
the cluster are not involved.

Both copies of the graph are checked: the export carries its nodes twice, at the top level and
inside ``activeVersion``, and a fix applied to one copy is a live bug.
"""

import json
import re
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]  # agents/n8n
WORKFLOWS = BASE / "workflows"
PROMPTS = BASE / "prompts"
CREATOR = WORKFLOWS / "article_creator.workflow.json"
REVIEW_PROMPT = PROMPTS / "article_review.md"

PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z_]+)\s*\}\}")
VAR_KEY_RE = re.compile(r'"([A-Z_]+)":')


def _copies():
    data = json.loads(CREATOR.read_text(encoding="utf-8"))
    yield "top level", data
    yield "activeVersion", data["activeVersion"]


def _nodes(document):
    return {node["name"]: node for node in document["nodes"]}


def _targets(document, source):
    block = document["connections"].get(source)
    if not block:
        return []
    return [edge["node"] for output in block["main"] for edge in output]


@pytest.mark.parametrize("label,document", list(_copies()))
def test_a_rejected_draft_is_regenerated_from_the_gate_reason(label, document):
    """The retry edge re-renders the drafting prompt, carrying the reviewer's reason.

    A retry that went straight back to the model would resubmit the same prompt, so a
    rejection for one reason could repeat until the bound, exactly as the LinkedIn gate did
    before 2026-09-30.
    """
    assert "download_article_prompt" in _targets(document, "switch_article_check"), (
        f"{label}: the rejected branch must return through download_article_prompt"
    )
    prompt = _nodes(document)["download_article_prompt"]["parameters"]["workflowInputs"]["value"][
        "template_vars"
    ]
    assert "$json.explanation" in prompt, f"{label}: the rerendered prompt must carry the gate reason"


@pytest.mark.parametrize("label,document", list(_copies()))
def test_gate_explanation_is_extracted(label, document):
    js = _nodes(document)["parse_article_check_output"]["parameters"]["jsCode"]
    assert "<explanation>" in js and "<output>" in js, f"{label}: verdict not extracted"


@pytest.mark.parametrize("label,document", list(_copies()))
def test_attempt_bound_counts_drafts(label, document):
    """MAX_TRIES must bound the drafts, so the loop cannot spin forever."""
    rules = _nodes(document)["switch_article_check"]["parameters"]["rules"]["values"]
    bound = [
        condition["leftValue"]
        for rule in rules
        for condition in rule["conditions"]["conditions"]
        if "MAX_TRIES" in condition.get("rightValue", "")
    ]
    assert bound == ["={{ $runIndex + 1 }}"], f"{label}: unexpected bound expression {bound}"
    assert _nodes(document)["set_workflow_vars"]["parameters"]["assignments"]["assignments"], label
    names = {a["name"] for a in _nodes(document)["set_workflow_vars"]["parameters"]["assignments"]["assignments"]}
    assert "MAX_TRIES" in names, f"{label}: MAX_TRIES is not set"


@pytest.mark.parametrize("label,document", list(_copies()))
def test_gate_failure_reports_its_reason(label, document):
    value = _nodes(document)["set_error_max_tries"]["parameters"]["assignments"]["assignments"][0][
        "value"
    ]
    assert value.startswith("="), f"{label}: ERROR is a literal, so the reason is lost"
    assert "MAX_RETRIES_EXCEEDED" in value and "explanation" in value, (
        f"{label}: ERROR must stay greppable as a gate failure and name a reason"
    )


@pytest.mark.parametrize("label,document", list(_copies()))
def test_an_over_budget_draft_is_retried_not_raised(label, document):
    """The budget is data the loop acts on, not a throw that ends the run.

    A count asked of a model is a count that gets invented, so the budget stays in code --
    but it must reject the draft for the retry rather than fail the run.
    """
    code = _nodes(document)["parse_article"]["parameters"]["jsCode"]
    assert "PROBLEM" in code, f"{label}: parse_article does not report a problem as data"
    assert "OVER_BUDGET" in code, f"{label}: the budget is no longer checked in code"
    assert "throw new Error('OVER_BUDGET" not in code, (
        f"{label}: an over-budget draft still throws instead of being retried"
    )


@pytest.mark.parametrize("label,document", list(_copies()))
def test_the_deterministic_budget_beats_the_reviewer(label, document):
    """The reviewer's opinion cannot override the parser's own numbers."""
    code = _nodes(document)["merge_article_verdict"]["parameters"]["jsCode"]
    assert "parse_article" in code and "PROBLEM" in code, (
        f"{label}: the verdict does not read the parser's deterministic problem"
    )
    assert "!problem" in code, f"{label}: a problem no longer rejects the draft outright"


@pytest.mark.parametrize("label,document", list(_copies()))
def test_the_reviewer_reads_the_rules_the_writer_followed(label, document):
    """One committed rules file, read by the drafter and the gate alike.

    A second copy of the rules would drift, and a gate enforcing a rule the drafter was never
    given is the failure of 2026-09-30 in a new place.
    """
    value = _nodes(document)["download_article_review_prompt"]["parameters"]["workflowInputs"][
        "value"
    ]
    assert value["template_name"] == "prompts/article_review.md", label
    assert "$('download_system_prompt')" in value["template_vars"], (
        f"{label}: the gate does not read the writer's own rules file"
    )


@pytest.mark.parametrize("label,document", list(_copies()))
def test_the_reviewer_is_a_model_pass_wired_to_both_models(label, document):
    node = _nodes(document)["check_article_llm"]
    assert node["type"] == "@n8n/n8n-nodes-langchain.chainLlm", label
    assert "download_article_review_prompt" in node["parameters"]["text"], label
    for model, index in (("ai_model", 0), ("ai_model_fallback", 1)):
        edges = document["connections"][model]["ai_languageModel"][0]
        hit = [e for e in edges if e["node"] == "check_article_llm"]
        assert hit and hit[0]["index"] == index, f"{label}: {model} does not feed the reviewer"


def test_review_prompt_placeholders_match_the_call():
    """DownloadTemplate stops the run for a name it was not handed, so the two halves must agree."""
    declared = {m.group(1) for m in PLACEHOLDER_RE.finditer(REVIEW_PROMPT.read_text(encoding="utf-8"))}
    value = json.loads(CREATOR.read_text(encoding="utf-8"))["nodes"]
    node = next(n for n in value if n["name"] == "download_article_review_prompt")
    supplied = set(VAR_KEY_RE.findall(node["parameters"]["workflowInputs"]["value"]["template_vars"]))
    assert declared == supplied
    assert {"TEXT", "WORD_COUNT", "MAX_WORDS", "RULES", "ASSET_TYPES"} <= declared


def test_both_prompt_files_name_the_same_marker_form():
    """A gate describing the marker differently from the drafter rejects a correct one.

    Measured live 2026-10-18 (executions 13892 and 13913): the check said "spelled as the
    type id", the reviewer read that as the bare id, rejected a correct
    `<!-- asset:image_wide -->` twice, and on the attempts that followed the writer dropped
    the marker altogether -- so the gate destroyed the thing it was checking. The publishing
    step is the authority: `build_commit_files` matches `<!--\\s*asset:<type>\\s*-->`.
    """
    writer = (PROMPTS / "article_writer.md").read_text(encoding="utf-8")
    reviewer = REVIEW_PROMPT.read_text(encoding="utf-8")
    form = "<!-- asset:<id> -->"
    assert form in writer, "the writer no longer states the marker form"
    assert form in reviewer, "the reviewer no longer states the marker form"
    assert "spelled as the type id" not in reviewer, (
        "the wording that made the reviewer reject a correct marker is back"
    )


def test_the_gate_checks_the_frame_the_tone_and_the_terms():
    """The objective half of the new rules is the half the gate is allowed to enforce.

    "Is it simple enough" is not a check — that judgement rejected four drafts for a Kubernetes
    subject on 2026-10-18 and cost a run. What can be checked is the close, the listed phrases and
    a term used before it is explained.
    """
    reviewer = REVIEW_PROMPT.read_text(encoding="utf-8")
    assert "The close points at what to read or do next" in reviewer, "the directional close is unchecked"
    assert "restates the article" in reviewer
    assert "No AI-speak from the list in the rules" in reviewer, "the tone list is unchecked"
    assert "is explained where it first appears" in reviewer, "the term rule is unchecked"
    assert "delve" not in reviewer, "the gate restates the banned list instead of reading the rules"


def test_the_reviewer_judges_only_the_checks_it_is_given():
    """An invented check is a rule the drafter cannot be told about.

    Measured 2026-10-18 (execution 14121): the gate enforced the entry's own description —
    "Plain language and no deep Kubernetes detail" — against a Kubernetes-native subject, and
    rejected four drafts for naming a custom resource, a controller, an admission webhook and
    Helm: the vocabulary the subject is made of, and which the writer's own rules invite by
    calling the reader a practitioner. No draft could satisfy it, so the run spent twenty
    minutes and its bound and then failed.
    """
    reviewer = REVIEW_PROMPT.read_text(encoding="utf-8")
    assert "Judge only the checks below" in reviewer, "the reviewer's scope is unbounded again"
    assert "not checks" in reviewer, "the entry's context can be enforced as a check again"
    assert "naming the primitives its subject is built from" in reviewer, (
        "a draft can be rejected again for naming the primitives its subject is built from"
    )


def test_the_reviewer_is_not_asked_for_an_h1_the_body_cannot_carry():
    """`parse_article` strips the H1 into TITLE, so the body can never contain one.

    Two of execution 14121's four rejections were "the first line must be the title as an H1" —
    a complaint the body cannot clear, and a drafting turn spent on each.
    """
    reviewer = REVIEW_PROMPT.read_text(encoding="utf-8")
    assert "the body only" in reviewer, "the reviewer no longer knows what it is reading"
    assert "an H1 is not required in it" in reviewer, "the H1 demand is back"
    # And the claim is true of the graph: the reviewer is handed the stripped body.
    node = next(n for n in json.loads(CREATOR.read_text(encoding="utf-8"))["nodes"]
                if n["name"] == "download_article_review_prompt")
    expr = node["parameters"]["workflowInputs"]["value"]["template_vars"]
    assert "\"TEXT\": $('parse_article').item.json.TEXT" in expr, (
        "the reviewer is no longer given the H1-stripped body this prompt describes"
    )


@pytest.mark.parametrize("label,document", list(_copies()))
def test_the_reviewer_retries_a_transient_model_failure(label, document):
    """The gate's own model call is retried, exactly as the LinkedIn lane's is.

    Measured live 2026-10-18: one 30 s LiteLLM timeout on `check_article_llm` ended a run
    that had already produced four drafts (execution 13975), while the node it mirrors --
    `check_rules_llm` in `LinkedIn Post Creator` -- carries `retryOnFail: true` with five
    tries, and the drafting agent in this workflow carries the same. A reviewer that fails
    the run it is checking is worse than one that reports no verdict.
    """
    node = _nodes(document)["check_article_llm"]
    assert node.get("retryOnFail") is True, f"{label}: the reviewer does not retry"
    assert node.get("maxTries") == 5, f"{label}: the reviewer's retry bound changed"
    assert node.get("waitBetweenTries") == 5000, f"{label}: the reviewer's retry wait changed"
