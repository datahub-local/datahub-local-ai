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
    # the prompt has to name the marker and not a path, filename or caption.
    text = TASK_PROMPT.read_text(encoding="utf-8")
    assert "<!-- asset:image -->" in text
    assert "<!-- asset:<id> -->" in text
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


def test_creator_fetches_both_prompt_files():
    assert _downloaded("download_article_prompt")[0] == "prompts/article_writer.md"
    assert _downloaded("download_system_prompt")[0] == "prompts/article_writer_system.md"


def test_creator_sends_the_system_prompt_as_the_system_message():
    # The persona and the hard rules must arrive as the system message, not as more
    # text in the user turn, or the model treats them as content to write about.
    message = _node("create_article_ai")["parameters"]["messages"]["messageValues"][0]["message"]
    assert "download_system_prompt" in message


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
