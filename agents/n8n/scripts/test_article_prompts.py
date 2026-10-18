"""Guard the article prompts' runtime interface.

`prompts/article_writer_system.md` and `prompts/article_writer.md` are fetched at runtime by
the `Article Creator` sub-workflow through the existing `DownloadTemplate` workflow. That
workflow scans the whole downloaded text for a doubled-curly-brace name and calls
`stop_and_error` for any name it was not handed, so a placeholder nobody supplies kills every
article run and only at runtime -- the same shape as the `image_motifs.json` note about a
comment mentioning one. So both halves of the contract are asserted here and against each
other: the names the prompts declare, the fact that the system prompt declares none at all
(it is fetched with an empty variable object), and the names `Article Creator` actually
passes.

`datasets/blog_categories.json` is fetched the same way with an empty variable object, so a
doubled brace anywhere in it, comments included, breaks every run.

The creator is a sub-workflow and carries no `settings.errorWorkflow`: the entry point
notifies and a sub-workflow raises, so one failure is reported once.
"""

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # agents/n8n
PROMPTS = BASE / "prompts"
DATASETS = BASE / "datasets"
WORKFLOWS = BASE / "workflows"

SYSTEM_PROMPT = PROMPTS / "article_writer_system.md"
TASK_PROMPT = PROMPTS / "article_writer.md"
CATEGORIES = DATASETS / "blog_categories.json"
CREATOR = WORKFLOWS / "article_creator.workflow.json"

PLACEHOLDER_RE = re.compile(r"\{\{(.*?)\}\}")
# The keys of an inline `template_vars` object literal, which is how every
# DownloadTemplate call in these exports is written.
VAR_KEY_RE = re.compile(r'"([A-Z_]+)":')

# What `Article Creator` must pass to article_writer.md, by name. Every name here is
# something the entry point already holds: the row's fields, the review feedback, the
# fetched link content and the resolved word budget.
CALLER_VARS = frozenset(
    {
        "TOPIC",
        "DESCRIPTION",
        "URL",
        "MAX_WORDS",
        "ASSET_TYPES",
        "EXTRA_PROMPT",
        "CONTENT",
        "FEEDBACK",
        "PREVIOUS_DRAFT",
    }
)

# The sub-workflow's own inputs, which the entry point must supply.
TRIGGER_VARS = frozenset(
    {
        "TOPIC",
        "DESCRIPTION",
        "URL",
        "CONTENT",
        "MAX_WORDS",
        "ASSET_TYPES",
        "EXTRA_PROMPT",
        "FEEDBACK",
    }
)


def _placeholders(path: Path) -> set:
    return {match.group(1).strip() for match in PLACEHOLDER_RE.finditer(path.read_text(encoding="utf-8"))}


def _creator() -> dict:
    return json.loads(CREATOR.read_text(encoding="utf-8"))


def _node(name: str) -> dict:
    for node in _creator()["nodes"]:
        if node["name"] == name:
            return node
    raise KeyError(name)


def _downloaded(name: str) -> tuple:
    """(template_name, template_vars keys) for a DownloadTemplate call node."""
    value = _node(name)["parameters"]["workflowInputs"]["value"]
    return value["template_name"], set(VAR_KEY_RE.findall(value["template_vars"]))


def test_system_prompt_declares_no_placeholder():
    # It is fetched with `template_vars: {}`, so any placeholder here is an
    # unresolvable name and DownloadTemplate stops the run.
    assert _placeholders(SYSTEM_PROMPT) == set()


def test_task_prompt_placeholders_are_the_caller_contract():
    assert _placeholders(TASK_PROMPT) == CALLER_VARS


def test_task_prompt_documents_the_asset_marker_contract():
    # The publish step replaces each marker in place and defaults a missing one, so
    # the prompt has to name the marker and not a path, filename or caption. The hero's
    # marker is the requested type's own id, not the literal `image`: the wide pair made
    # `<!-- asset:image -->` a marker no row asks for, and the review gate now rejects a
    # draft whose markers do not match the requested set.
    text = TASK_PROMPT.read_text(encoding="utf-8")
    assert "<!-- asset:<id> -->" in text
    assert "<!-- asset:image -->" not in text
    assert "ASSET_TYPES" in _placeholders(TASK_PROMPT)
    assert "no caption" in text


def test_task_prompt_states_the_word_budget():
    text = TASK_PROMPT.read_text(encoding="utf-8")
    assert "MAX_WORDS" in _placeholders(TASK_PROMPT)
    assert "Length budget" in text


def test_task_prompt_keeps_feedback_highest_priority():
    # The retry carries the reviewer's own words back in; a prompt that buries them
    # below the shape rules produces the same rejection twice.
    text = TASK_PROMPT.read_text(encoding="utf-8")
    assert "HIGHEST PRIORITY" in text
    assert text.index("## Reviewer Feedback") < text.index("## Shape")


def test_categories_are_a_unique_non_empty_list():
    categories = json.loads(CATEGORIES.read_text(encoding="utf-8"))["categories"]
    assert categories
    assert all(isinstance(name, str) and name.strip() for name in categories)
    assert len(set(categories)) == len(categories)


def test_categories_carry_the_seeded_taxonomy():
    categories = json.loads(CATEGORIES.read_text(encoding="utf-8"))["categories"]
    assert set(categories) == {"General", "Learning", "OSS", "Datahub.local"}


def test_categories_have_no_placeholder():
    # Fetched with an empty template_vars, and the scan does not skip comments.
    text = CATEGORIES.read_text(encoding="utf-8")
    assert "{{" not in text and "}}" not in text


def test_creator_passes_what_the_task_prompt_declares():
    """The two halves of the contract, checked against each other rather than a list."""
    _name, supplied = _downloaded("download_article_prompt")
    assert supplied == _placeholders(TASK_PROMPT)


def test_the_retry_carries_the_draft_the_review_rejected():
    """The retry edits the draft it was told to fix instead of writing a new one.

    A retry re-renders this prompt with the reviewer's reason and nothing else, so a model told
    to "remove the closing paragraph" had no draft to remove it from — and on 2026-10-18 it went
    looking for material instead, calling the same search seven times and the same page six times
    until the agent's iteration cap killed the run (executions 14018, 14020).
    """
    expr = _node("download_article_prompt")["parameters"]["workflowInputs"]["value"]["template_vars"]
    assert "PREVIOUS_DRAFT" in expr
    assert "$('parse_article').last()" in expr, "the retry must carry the draft just rejected"
    assert "$('parse_article').item" not in expr, (
        "the loop's paired-item lineage runs back through switch_article_check and cannot resolve"
    )
    assert "$('parse_article').first()" not in expr, (
        "a third attempt would edit the first attempt's draft and never converge"
    )
    assert "isExecuted" in expr, "an unguarded read throws when the first attempt renders this"


def test_creator_fetches_both_prompt_files():
    assert _downloaded("download_article_prompt")[0] == "prompts/article_writer.md"
    assert _downloaded("download_system_prompt")[0] == "prompts/article_writer_system.md"


# A tool node's type is not free. The v3.1 agent hands a tool call to the workflow engine, which
# runs the node through its own executor and therefore needs an `execute` method. In this build
# `toolHttpRequest` has only `supplyData`, so every call to it died with
#   The node "@n8n/n8n-nodes-langchain.toolHttpRequest" has a "supplyData" method but no "execute" method.
# and the draft came back `EMPTY_DRAFT` after the model had spent its turns on a tool that could
# not run (execution 13598, 2026-10-16). The list is read off the installed image:
#   grep -L "async execute" n8n-nodes-langchain/dist/nodes/tools/*/*.node.js
EXECUTABLE_TOOL_TYPES = frozenset(
    {
        "@n8n/n8n-nodes-langchain.toolWorkflow",
        "@n8n/n8n-nodes-langchain.toolWikipedia",
        "@n8n/n8n-nodes-langchain.toolSearXng",
        "@n8n/n8n-nodes-langchain.toolSerpApi",
        "@n8n/n8n-nodes-langchain.toolWolframAlpha",
        "@n8n/n8n-nodes-langchain.toolCode",
        "@n8n/n8n-nodes-langchain.toolThink",
        "@n8n/n8n-nodes-langchain.toolVectorStore",
    }
)


def _writer_tools() -> set:
    return {
        name
        for name, kinds in _creator()["connections"].items()
        for branches in (kinds.get("ai_tool") or [])
        for edge in branches or []
        if edge["node"] == "create_article_ai"
    }


def test_creator_gives_the_writer_its_persona_and_its_tools():
    # The writer is an agent (tools on the writer, chosen deliberately), so the persona rides
    # in the prompt text: the node's system slot is a parameter this repository has never used,
    # and one wrong key would drop the persona without failing anything.
    node = _node("create_article_ai")
    assert node["type"] == "@n8n/n8n-nodes-langchain.agent"
    assert "download_system_prompt" in node["parameters"]["text"]
    assert "download_article_prompt" in node["parameters"]["text"]
    assert _writer_tools() == {"research_sources", "read_page"}


def test_the_writer_loop_is_bounded():
    # Measured on execution 13603: the primary model failed three times with
    # `Cannot read properties of undefined (reading 'map')` and every fallback rescue spends one
    # iteration, so a budget of 8 was gone before the draft was written.
    iterations = _node("create_article_ai")["parameters"]["options"]["maxIterations"]
    assert isinstance(iterations, int)
    assert 8 <= iterations <= 20


def test_every_writer_tool_can_be_executed_by_the_agent():
    for name in _writer_tools():
        assert _node(name)["type"] in EXECUTABLE_TOOL_TYPES, name
        assert "@n8n/n8n-nodes-langchain.toolHttpRequest" != _node(name)["type"]


def test_the_writer_researches_through_workflows_in_this_repository():
    # Both tools wrap a workflow in this repository, so the HTTP detail lives in one place and
    # the model receives a digest rather than two raw API payloads.
    research = _node("research_sources")["parameters"]
    content_research = json.loads((WORKFLOWS / "content_research.workflow.json").read_text(encoding="utf-8"))
    assert research["workflowId"]["value"] == content_research["id"]
    assert research["workflowId"]["cachedResultName"] == content_research["name"]
    assert "QUERY" in research["workflowInputs"]["value"]
    page = _node("read_page")["parameters"]
    assert page["workflowId"]["value"] == "09xEuVQj207pjK4x"  # Download Content, readable text
    for name in _writer_tools():
        assert _node(name)["parameters"].get("description")


def test_task_prompt_bounds_and_scopes_the_research():
    text = TASK_PROMPT.read_text(encoding="utf-8")
    assert "`research_sources`" in text and "`read_page`" in text
    assert "three lookups" in text
    # A name match is not a subject match: on the first live run every result for "Sympozium"
    # was about a different Symposium, and only this rule stops the model hunting for one.
    assert "same-named" in text
    assert "never cite a URL you did not fetch" in text


def test_creator_returns_text_its_title_and_the_error_field():
    names = {a["name"] for a in _node("set_output")["parameters"]["assignments"]["assignments"]}
    assert {"text", "title", "word_count", "ERROR"} <= names


def test_creator_declares_every_input_the_entry_point_sends():
    declared = {v["name"] for v in _node("main_trigger")["parameters"]["workflowInputs"]["values"]}
    assert declared == TRIGGER_VARS


def test_creator_raises_instead_of_notifying():
    # A sub-workflow leaves settings.errorWorkflow unset so its failure propagates to
    # the entry point, which reports once with its own context.
    assert "errorWorkflow" not in _creator()["settings"]


def test_creator_enforces_the_budget_itself():
    code = _node("parse_article")["parameters"]["jsCode"]
    assert "MAX_WORDS" in code
    assert "OVER_BUDGET" in code
    assert "EMPTY_DRAFT" in code
