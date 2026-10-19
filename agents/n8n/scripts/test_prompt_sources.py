"""Every model-facing instruction lives in a prompt file or the authoring brief.

The rule is in AGENTS.md: a prompt file under ``agents/n8n/`` fetched by
``DownloadTemplate``, or the brief assembled from it. An inline instruction in a Code
node, a model node's text, an HTTP body or a tool description is a gap: the model reads
it, a reviewer does not, and editing the prompt file cannot fix it.

The graph cannot say where a string was authored, so this asserts the traceable half:
every model call resolves to a fetched template (directly, through its input, or through
a builder named below with the reason), every template target exists, and the allowance
list stays short and justified. Both copies of every export are checked.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"

# A node that turns a fetched prompt file into a model request. Every entry is a reviewed
# exception: the node names the prompt file it reads, and no instruction is authored in it.
BUILDERS = {
    ("image_content_generator", "Apply: Style to Prompt"):
        "fills prompts/diagram_prompt_prefill.md, which the edit form shows before sending",
    ("image_content_generator", "Prepare: Prompt Retry"):
        "re-sends the same fetched prompt with the reviewer's feedback in its slot",
    ("visual_studio", "encode_stills"):
        "joins prompts/visual_review_composition.md with the brief it judges",
    ("visual_studio", "prepare_raster_review"):
        "joins prompts/visual_review_raster.md with the prompt and text it judges",
}

# A model call whose prompt is human input rather than an authored instruction.
HUMAN_INPUT = {
    ("image_content_generator", "generate_image"):
        "the prompt is the edit-form value a person approves before it is sent",
}

MODEL_TYPES = ("chainLlm", ".agent")


def _copies(path):
    doc = json.loads(path.read_text())
    yield "top", doc
    av = doc.get("activeVersion")
    if isinstance(av, dict) and "nodes" in av:
        yield "activeVersion", av


def _exports():
    for path in sorted(WORKFLOWS.glob("*.json")):
        name = path.name.removesuffix(".workflow.json")
        for label, doc in _copies(path):
            yield name, label, doc


def _node(doc, name):
    for n in doc["nodes"]:
        if n["name"] == name:
            return n
    return None


def _model_nodes(doc):
    for n in doc["nodes"]:
        if any(m in n.get("type", "") for m in MODEL_TYPES):
            yield n


def _source_of(doc, name):
    """The node feeding ``name`` over main input 0, or None."""
    for src, outputs in doc.get("connections", {}).items():
        for branch in outputs.get("main", []):
            for edge in branch or []:
                if edge.get("node") == name and edge.get("index", 0) == 0:
                    return src
    return None


def _template_of(doc, name):
    """A DownloadTemplate call's target path, or None."""
    node = _node(doc, name)
    if not node or not node.get("type", "").endswith("executeWorkflow"):
        return None
    value = (node.get("parameters", {}).get("workflowInputs") or {}).get("value") or {}
    name_value = value.get("template_name")
    return name_value.lstrip("=") if isinstance(name_value, str) else None


def _builder_ancestor(doc, name, workflow):
    """The nearest reviewed builder feeding ``name``, across pass-through gates."""
    seen = set()
    source = _source_of(doc, name)
    while source and source not in seen:
        seen.add(source)
        if (workflow, source) in BUILDERS:
            return source
        source = _source_of(doc, source)
    return None


def _node_text(node):
    params = node.get("parameters", {}) or {}
    out = [params.get("text")]
    for message in (params.get("messages") or {}).get("messageValues", []) or []:
        out.append(message.get("message"))
    return [t for t in out if isinstance(t, str) and t.strip()]


@pytest.mark.parametrize("workflow,label,doc", list(_exports()))
def test_every_downloaded_prompt_exists(workflow, label, doc):
    for node in doc["nodes"]:
        target = _template_of(doc, node["name"])
        if not target:
            continue
        assert (ROOT / target).is_file(), f"{workflow}/{label}: {node['name']} downloads missing {target}"


@pytest.mark.parametrize("workflow,label,doc", list(_exports()))
def test_every_model_call_reads_a_prompt_file(workflow, label, doc):
    for node in _model_nodes(doc):
        for text in _node_text(node):
            # A fetched prompt, referenced by name.
            if re.search(r"\$\('download_[^']+'\)", text):
                continue
            # The node's own input is a DownloadTemplate call.
            source = _source_of(doc, node["name"])
            if source and _template_of(doc, source):
                continue
            # A reviewed builder that fills a fetched prompt.
            if (workflow, source) in BUILDERS and "$json" in text:
                continue
            raise AssertionError(
                f"{workflow}/{label}: {node['name']} has a prompt that resolves to no "
                f"prompt file (source={source!r}, text={text[:120]!r})"
            )


@pytest.mark.parametrize("workflow,label,doc", list(_exports()))
def test_every_tool_description_reads_a_prompt_file(workflow, label, doc):
    for node in doc["nodes"]:
        if not node.get("type", "").endswith("toolWorkflow"):
            continue
        description = (node.get("parameters", {}) or {}).get("description")
        assert isinstance(description, str) and description.strip(), (
            f"{workflow}/{label}: {node['name']} has no description"
        )
        match = re.search(r"\$\('([^']+)'\)", description)
        assert match, (
            f"{workflow}/{label}: {node['name']} describes itself inline; "
            "put the text in a prompt file"
        )
        source = match.group(1)
        upstream = _source_of(doc, source) or source
        target = _template_of(doc, source) or _template_of(doc, upstream)
        assert target, (
            f"{workflow}/{label}: {node['name']} reads {source}, which downloads no prompt file"
        )


@pytest.mark.parametrize("workflow,label,doc", list(_exports()))
def test_every_model_http_body_comes_from_a_prompt_file(workflow, label, doc):
    for node in doc["nodes"]:
        if not node.get("type", "").endswith("httpRequest"):
            continue
        if "chat/completions" not in json.dumps(node.get("parameters", {})):
            continue
        if (workflow, node["name"]) in HUMAN_INPUT:
            continue
        body = (node.get("parameters", {}) or {}).get("jsonBody", "")
        match = re.search(r"\$\('([^']+)'\)", body)
        # `$json.X` is built by the node feeding this one, which is the one to review.
        source = match.group(1) if match else _builder_ancestor(doc, node["name"], workflow)
        assert source, f"{workflow}/{label}: {node['name']} sends an inline body"
        assert (workflow, source) in BUILDERS, (
            f"{workflow}/{label}: {node['name']} sends a body built by {source!r}, "
            "which is not a reviewed prompt builder"
        )


def test_the_allowances_are_still_real_and_justified():
    # An allowance that no longer matches a live node is a stale exception that will hide
    # the next inline prompt at that name.
    seen = {(workflow, node) for workflow, _, doc in _exports() for node in (n["name"] for n in doc["nodes"])}
    for workflow, node in list(BUILDERS) + list(HUMAN_INPUT):
        assert (workflow, node) in seen, f"allowance names a node that does not exist: {workflow}/{node}"
    for (workflow, node), reason in list(BUILDERS.items()) + list(HUMAN_INPUT.items()):
        assert reason and len(reason) > 20, f"{workflow}/{node} needs a written reason"


def test_the_visual_brief_reads_the_scene_contract():
    # The definition of a scene is a prompt file, not a count: run 14335 opened cold.
    doc = json.loads((WORKFLOWS / "visual_studio.workflow.json").read_text())
    brief = _node(doc, "build_author_brief")["parameters"]["jsCode"]
    assert "$('scene_rules')" in brief
    text = (ROOT / "prompts" / "visual_scene.md").read_text()
    assert "A scene is one beat" in text
