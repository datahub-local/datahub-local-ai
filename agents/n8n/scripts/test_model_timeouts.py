"""Guard every model node's request budget.

The model nodes call a LiteLLM gateway that has a **fallback chain**: a primary that stalls is not
a failed call, because the gateway waits on it and then fails over. The client therefore has to
outlast the whole failover, or it abandons the call during it and reports a timeout the gateway
never made. On 2026-10-18 that is what ended execution 13975's reviewer turn —
`litellm.Timeout: Timeout passed=30.0` — and the article lane's `check_article_llm` has carried a
retry ever since.

The node's own default is 60000 ms, read off the installed image
(`.../nodes/llms/LMChatOpenAi/LmChatOpenAi.node.js`, the `timeout` option, applied both to the
undici dispatcher and to the LangChain client). Neither the credential nor the instance carries a
timeout, so the budget lives on each node, and the check is a sweep: a per-file assertion would be
one copy of the rule per workflow, and a new workflow would be silently exempt.

Both copies of every export are checked, because an export carries its nodes twice.
"""

import json
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
MODEL_TYPE = "@n8n/n8n-nodes-langchain.lmChatOpenAi"

# The top of the failover budget the owner named: enough for the gateway's own per-attempt
# timeout on the primary plus a fallback attempt plus overhead.
FLOOR_MS = 120000

EXPECTED_FILES = {
    "article_creator.workflow.json",
    "content_feed_curator.workflow.json",
    "image_content_generator.workflow.json",
    "linked_in_image_creator.workflow.json",
    "linked_in_post_creator.workflow.json",
    "visual_studio.workflow.json",
}


def _model_nodes():
    for path in sorted(WORKFLOWS.glob("*.workflow.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for label, nodes in (
            ("nodes", data.get("nodes")),
            ("activeVersion.nodes", (data.get("activeVersion") or {}).get("nodes")),
        ):
            for node in nodes or []:
                if node.get("type") == MODEL_TYPE:
                    yield f"{path.name} [{label}] {node['name']}", node


def test_the_sweep_finds_the_model_nodes():
    """A sweep that finds nothing passes for the wrong reason.

    A workflow that stops declaring a model node, or a node type that changes, would make the
    budget check vacuous rather than failing it.
    """
    found = list(_model_nodes())
    assert len(found) >= 12, f"expected the repository's model nodes, found {len(found)}"
    missing = EXPECTED_FILES - {where.split()[0] for where, _ in found}
    assert not missing, f"the sweep no longer reaches {sorted(missing)}"


def test_every_model_node_waits_for_the_gateway_failover():
    short = []
    for where, node in _model_nodes():
        timeout = (node.get("parameters", {}).get("options") or {}).get("timeout")
        if not isinstance(timeout, int) or timeout < FLOOR_MS:
            short.append(f"{where}: timeout={timeout!r}")
    assert not short, (
        "these model nodes would abandon a call the gateway is still failing over "
        f"(floor {FLOOR_MS} ms):\n" + "\n".join(short)
    )
