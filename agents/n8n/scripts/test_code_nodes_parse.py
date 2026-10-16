"""Guard every n8n Code node against a JavaScript syntax error.

An export's ``jsCode`` is text, so nothing offline could tell a valid program from
a broken one: a doubled escape -- two backslashes written where a line break was
meant -- leaves valid JSON, a readable diff and every textual assertion passing, and
fails only when n8n parses the node, where a parse error takes the whole node out
for every run. That happened on 2026-10-16 to ``build_author_brief``: the branch
adding a still type put ``\\n`` between two statements instead of a newline, the live
apply shipped it, and every agent-authored asset would have failed with a syntax
error the moment a run reached the node.

n8n runs a Code node inside an async wrapper, so the body is checked inside one: a
top-level ``return`` and a top-level ``await`` are legal there and illegal in a
plain script, so checking the raw text would report errors that are not.

Both copies of every export are checked. node is required rather than optional: a
check that silently skips when its tool is missing is the same failure it exists to
catch.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"

NODE_REQUIRED = "node is required to parse the exports' Code nodes"


def _code_nodes():
    for path in sorted(WORKFLOWS.glob("*.workflow.json")):
        data = json.loads(path.read_text())
        for label, nodes in (
            ("nodes", data.get("nodes")),
            ("activeVersion.nodes", (data.get("activeVersion") or {}).get("nodes")),
        ):
            for node in nodes or []:
                code = (node.get("parameters") or {}).get("jsCode")
                if isinstance(code, str) and code.strip():
                    yield f"{path.name} [{label}] {node['name']}", code


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_every_code_node_parses():
    failures = []
    for where, code in _code_nodes():
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write("async function __n8n(){\n" + code + "\n}\n")
            name = fh.name
        try:
            done = subprocess.run(["node", "--check", name], capture_output=True, text=True, check=False)
        finally:
            Path(name).unlink()
        if done.returncode != 0:
            first = next((line for line in done.stderr.splitlines() if line.strip()), "")
            failures.append(f"{where}: {first.strip()}")
    assert not failures, "Code node(s) that do not parse:\n" + "\n".join(failures)
