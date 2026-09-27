"""Guard the Respond to Webhook exports against an option the node rejects.

Every export carries its nodes twice (top level and inside ``activeVersion``),
so both are checked. The bug this locks down: a node was saved with
``respondWith: "html"``, which n8n's Respond to Webhook does not support -- it
throws ``The Response Data option "html" is not supported!`` at run time, after
the branch has already done its work, so the browser gets no page. HTML belongs
in a ``text`` response with a ``Content-Type: text/html`` header, and ``text``
needs a ``responseBody`` to say which field holds the page.

The network is not involved; these run on the committed export files.
"""

import json
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"

SUPPORTED = {
    "allIncomingItems",
    "binary",
    "firstIncomingItem",
    "json",
    "jwt",
    "noData",
    "redirect",
    "text",
}


def _respond_nodes(path):
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        return
    for label, nodes in (
        ("nodes", data.get("nodes")),
        ("activeVersion.nodes", (data.get("activeVersion") or {}).get("nodes")),
    ):
        for node in nodes or []:
            if node.get("type") == "n8n-nodes-base.respondToWebhook":
                yield label, node


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.workflow.json")), ids=lambda p: p.name)
def test_respond_to_webhook_options(path):
    for label, node in _respond_nodes(path):
        params = node.get("parameters", {})
        respond_with = params.get("respondWith")
        where = f"{path.name} [{label}] {node['name']}"
        assert respond_with in SUPPORTED, f"{where}: respondWith={respond_with!r} is not supported"
        if respond_with == "text":
            assert params.get("responseBody"), f"{where}: text response has no responseBody"
