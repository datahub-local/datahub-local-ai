"""The improvement pass's aspect registry and its fan-out.

The aspects are data: `datasets/article_aspects.json` lists them, each pointing at its own
prompt file, and the graph holds no aspect id. That is the whole point of the registry shape —
adding an aspect is a dataset entry plus a prompt file — and it is also its failure mode: a
graph that quietly holds an id, or a splitter that fans out from a list it did not read, looks
identical until an aspect silently stops running.

Offline: the committed exports and datasets, plus the three Code nodes whose decisions are
invisible in the graph (the fan-out, the merge, and the fatal registry check). Both copies of
every graph are checked where the export carries two.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parents[1]
ENTRY = AGENTS / "workflows" / "article_content_writer.workflow.json"
REGISTRY = AGENTS / "datasets" / "article_aspects.json"
NODE_REQUIRED = "node is required to execute a Code node's decisions"

RUNNER = r"""
async function __n8n_main__() {
  const stubs = JSON.parse(process.env.STUBS || '{}');
  const $ = (name) => {
    // n8n answers an unexecuted node with a proxy: `isExecuted` is false and any read throws.
    if (!(name in stubs.nodes)) return { isExecuted: false };
    const items = stubs.nodes[name].map((json) => ({ json }));
    return {
      isExecuted: true,
      first: () => items[0],
      last: () => items[items.length - 1],
      all: () => items,
      item: items[0],
    };
  };
  const $input = { all: () => ((stubs.input || []).map((json) => ({ json }))) };
  const $json = (stubs.input || [{}])[0];
  const $runIndex = stubs.run_index || 0;
  const console = { log: () => {}, warn: () => {}, error: () => {} };
  const __result = await (async () => {
__CODE__
  })();
  process.stdout.write(JSON.stringify(__result));
}
__n8n_main__().catch((e) => { process.stderr.write(String((e && e.message) || e)); process.exit(1); });
"""


def _doc():
    return json.loads(ENTRY.read_text(encoding="utf-8"))


def _node(name):
    return next(n for n in _doc()["nodes"] if n["name"] == name)


def _js(name):
    return _node(name)["parameters"]["jsCode"]


def _run(code, nodes=None, input_=None, run_index=0):
    src = RUNNER.replace("__CODE__", code)
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as fh:
        fh.write(src)
        path = fh.name
    env = dict(
        os.environ,
        STUBS=json.dumps({"nodes": nodes or {}, "input": input_ or [], "run_index": run_index}),
    )
    try:
        done = subprocess.run(["node", path], capture_output=True, text=True, env=env, check=False)
    finally:
        Path(path).unlink()
    return done


def _items(done):
    assert done.returncode == 0, done.stderr
    return [item["json"] for item in json.loads(done.stdout)]


# ------------------------------------------------------------------ the registry

def test_the_registry_parses_and_names_a_prompt_and_a_focus():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    aspects = data["aspects"]
    assert [a["id"] for a in aspects] == ["structure", "clarity", "flow"]
    for aspect in aspects:
        assert (AGENTS / aspect["prompt"]).is_file(), aspect["prompt"]
        assert aspect["focus"].strip(), aspect["id"]
        # Fetched with an empty vars object? No: the vars are the aspect's own, but the path is
        # a repository path, so a doubled brace here would be a path, not a variable.
        assert "{{" not in aspect["prompt"]


def test_the_registry_itself_has_no_placeholder():
    # It is fetched with an empty vars object, and DownloadTemplate scans comments too.
    text = REGISTRY.read_text(encoding="utf-8")
    assert "{{" not in text and "}}" not in text


# ------------------------------------------------------------------ the graph

def test_the_graph_reads_the_registry_and_holds_no_aspect_id():
    doc = _doc()
    fetch = _node("download_article_aspects")["parameters"]["workflowInputs"]["value"]
    assert fetch["template_name"] == "datasets/article_aspects.json"
    assert fetch["template_vars"] == "={{ {} }}"
    assert "download_article_aspects" in _js("build_improvement_context")
    assert "download_article_aspects" in _js("build_improvement_context")
    # the fan-out reads the item the registry check emitted, not a literal list
    split = _js("split_aspects")
    assert "$('build_improvement_context')" in split and ".ASPECTS" in split
    # the prompt file is chosen per aspect by expression, so no aspect id is in the graph
    downloaded = _node("download_aspect_prompt")["parameters"]["workflowInputs"]["value"]
    assert downloaded["template_name"] == "={{ $json.ASPECT_PROMPT }}"
    assert "ASPECT_PROMPT" in json.dumps(doc), "the fan-out no longer carries its prompt path"
    blob = json.dumps(doc)
    for aspect in ("structure", "clarity", "flow"):
        assert f'"prompt": "prompts/article_aspect_{aspect}.md"' not in blob
        assert f"article_aspect_{aspect}" not in blob, f"the graph hardcodes the {aspect} prompt"


def test_the_improvement_chain_is_wired_in_order():
    conn = _doc()["connections"]

    def targets(source, output=0):
        branches = (conn.get(source) or {}).get("main") or []
        return [e["node"] for e in (branches[output] if output < len(branches) else [])]

    chain = [
        ("read_draft_for_improvement", "download_article_aspects"),
        ("download_article_aspects", "download_article_audiences"),
        ("download_article_audiences", "download_article_structures"),
        ("download_article_structures", "download_ai_speak"),
        ("download_ai_speak", "download_writer_rules"),
        ("download_writer_rules", "build_improvement_context"),
        ("build_improvement_context", "split_aspects"),
        ("split_aspects", "download_aspect_prompt"),
        ("download_aspect_prompt", "review_aspect_llm"),
        ("review_aspect_llm", "merge_aspect_findings"),
        ("merge_aspect_findings", "if_has_findings"),
    ]
    for source, target in chain:
        assert targets(source) == [target], f"{source} -> {target}"
    assert targets("if_has_findings", 0) == ["download_improver_prompt"]
    assert targets("if_has_findings", 1) == ["select_final_draft"], "nothing to apply must pass through"
    assert targets("download_improver_prompt") == ["improve_article"]
    assert targets("improve_article", 0) == ["check_improved_draft"]
    assert targets("improve_article", 1) == ["select_final_draft"], "a failed improver falls back"
    assert targets("check_improved_draft") == ["switch_improved_ok"]
    assert targets("switch_improved_ok", 0) == ["select_final_draft"]
    assert targets("switch_improved_ok", 1) == ["select_final_draft"]
    assert targets("switch_improved_ok", 2) == ["download_improver_prompt"], "the retry re-renders"
    # One reviewer per aspect, never a switch between the fan-out and the merge.
    assert targets("split_aspects") == ["download_aspect_prompt"]
    assert len((conn.get("download_aspect_prompt") or {}).get("main") or []) == 1
    # The convergence node feeds the chain that stores and uploads the draft. This edge was
    # missing when the chain replaced the old `check_draft_error -> derive_slug` edge: execution
    # 14382 (2026-10-19) improved the draft, ended at `select_final_draft` as `success`, and
    # stored, uploaded and reviewed nothing.
    assert targets("select_final_draft") == ["derive_slug"]
    assert targets("derive_slug") == ["store_draft"]
    seen, queue = {"select_final_draft"}, ["select_final_draft"]
    while queue:
        for nxt in targets(queue.pop()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    assert "notify_article_review" in seen, "the improved draft does not reach the review"


def test_the_improver_is_an_agent_with_no_tools_and_both_models():
    node = _node("improve_article")
    assert node["type"] == "@n8n/n8n-nodes-langchain.agent"
    assert node.get("onError") == "continueErrorOutput", "a failed improver must not kill the run"
    assert node["parameters"]["options"]["maxIterations"] == 8, "the measured no-tools floor"
    assert "download_improver_prompt" in node["parameters"]["text"]
    assert "download_writer_rules" in node["parameters"]["text"]
    tools = {
        source
        for source, kinds in _doc()["connections"].items()
        for branch in kinds.get("ai_tool") or []
        for edge in branch or []
        if edge["node"] == "improve_article"
    }
    assert not tools, f"the improver has tools attached: {sorted(tools)}"
    for model, index in (("improve_model", 0), ("improve_model_fallback", 1)):
        edges = _doc()["connections"][model]["ai_languageModel"][0]
        hit = {e["node"]: e["index"] for e in edges}
        assert hit.get("review_aspect_llm") == index, model
        assert hit.get("improve_article") == index, model


def test_the_aspect_chain_retries_a_transient_failure():
    node = _node("review_aspect_llm")
    assert node["type"] == "@n8n/n8n-nodes-langchain.chainLlm"
    assert node.get("retryOnFail") is True
    assert node.get("maxTries") == 5
    assert node.get("waitBetweenTries") == 5000
    assert node.get("onError") == "continueRegularOutput"


# ------------------------------------------------------------------ the nodes

@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_the_fan_out_emits_one_item_per_registry_aspect():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    context = _items(_run(_js("build_improvement_context"), {
        "select_article_to_queue": [{"ENTRY_ID": "e1", "MAX_WORDS": 1200,
                                     "REQUESTED_ASSETS": "svg_wide", "AUDIENCE": "LOW"}],
        "read_draft_for_improvement": [{}],
        "execute_article_creator": [{"text": "Body text.", "title": "A Title"}],
        "download_article_aspects": [{"output": REGISTRY.read_text(encoding="utf-8")}],
        "download_article_audiences": [{"output": "levels"}],
        "download_article_structures": [{"output": "shapes"}],
        "download_writer_rules": [{"output": "rules"}],
    }))[0]
    assert [a["ASPECT"] for a in context["ASPECTS"]] == ["structure", "clarity", "flow"]
    assert context["ASPECTS"][0]["ASPECT_PROMPT"] == registry["aspects"][0]["prompt"]
    out = _items(_run(_js("split_aspects"), {"build_improvement_context": [context]}))
    assert [i["ASPECT"] for i in out] == ["structure", "clarity", "flow"]
    assert all(i["ASPECT_PROMPT"].startswith("prompts/article_aspect_") for i in out)
    assert all(i["ENTRY_ID"] == "e1" for i in out), "the row fields must ride on every item"


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_a_broken_registry_is_fatal():
    """Without its definitions the pass must not run quietly on no aspects."""
    base = {
        "select_article_to_queue": [{"ENTRY_ID": "e1", "MAX_WORDS": 1200, "REQUESTED_ASSETS": "svg_wide"}],
        "read_draft_for_improvement": [{}],
        "execute_article_creator": [{"text": "Body.", "title": "T"}],
        "download_article_audiences": [{"output": "levels"}],
        "download_article_structures": [{"output": "shapes"}],
        "download_writer_rules": [{"output": "rules"}],
    }
    for registry in ("", "not json", "{}", '{"aspects": []}'):
        nodes = dict(base, download_article_aspects=[{"output": registry}])
        done = _run(_js("build_improvement_context"), nodes)
        assert done.returncode != 0, f"an empty registry ({registry!r}) did not stop the run"
        assert "article_aspects.json" in done.stderr or "no usable aspect" in done.stderr, done.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_the_findings_are_tagged_by_aspect_and_none_contributes_nothing():
    ctx = {"ENTRY_ID": "e1", "HAS_FEEDBACK": False}
    aspects = [
        {"ASPECT": "structure", "FOCUS": "the plot"},
        {"ASPECT": "clarity", "FOCUS": "the terms"},
        {"ASPECT": "flow", "FOCUS": "the pacing"},
    ]
    result = _run(_js("merge_aspect_findings"), {
        "build_improvement_context": [ctx],
        "split_aspects": aspects,
        "review_aspect_llm": [
            {"text": "text structure <findings>1. Opening: buries the point — lead with it\n2. Close: restates — cut it</findings> more"},
            {"text": "<findings>none</findings>"},
            {"text": ""},  # the call failed and forwarded nothing usable
        ],
    })
    out = _items(result)[0]
    assert "### structure (the plot)" in out["FINDINGS"]
    assert "clarity" not in out["FINDINGS"] and "flow" not in out["FINDINGS"]
    assert out["HAS_FINDINGS"] is True
    assert out["FINDINGS_SUMMARY"] == "structure: 2, clarity: none, flow: none", out["FINDINGS_SUMMARY"]
    assert out["HAS_ANY"] is True


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_a_failed_aspect_forwards_its_prompt_but_contributes_nothing():
    """The reviewer's failure path forwards its input, which is the prompt asking for `none`."""
    ctx = {"ENTRY_ID": "e1", "HAS_FEEDBACK": False}
    prompt = "Return <findings>none</findings> when the body is sound."
    out = _items(_run(_js("merge_aspect_findings"), {
        "build_improvement_context": [ctx],
        "split_aspects": [{"ASPECT": "structure", "FOCUS": ""}],
        "review_aspect_llm": [{"output": prompt}],
    }))[0]
    assert out["FINDINGS"] == ""
    assert out["HAS_FINDINGS"] is False
    assert out["HAS_ANY"] is False
