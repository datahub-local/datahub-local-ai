"""Guard n8n expression parameters against a truncated object/array literal.

Every export carries its nodes twice (top level and inside ``activeVersion``),
so both are checked. The bug this locks down: an edit that swaps an inline
value for a node reference dropped the key's neighbours and the closing braces,
leaving ``={{ { ... ,`` -- an unterminated expression n8n rejects at run time
with ``ExpressionExtensionError: invalid syntax``. A truncated string is still
valid JSON, so nothing else catches it.

Only expressions whose body is a single ``{...}`` or ``[...]`` literal are
checked; a URL such as ``={{ $env.X }}/v1`` legitimately ends with more text.
"""

import json
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"


def _values(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _values(item)
    elif isinstance(value, str):
        yield value


def _literal_expressions(path):
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        return
    for label, nodes in (
        ("nodes", data.get("nodes")),
        ("activeVersion.nodes", (data.get("activeVersion") or {}).get("nodes")),
    ):
        for node in nodes or []:
            for value in _values(node.get("parameters", {})):
                text = value.strip()
                if not text.startswith("={{"):
                    continue
                body = text[len("={{") :].strip()
                if body[:1] in ("{", "["):
                    yield f"{path.name} [{label}] {node['name']}", text


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.workflow.json")), ids=lambda p: p.name)
def test_object_and_array_expressions_are_terminated(path):
    for where, text in _literal_expressions(path):
        assert text.endswith("}}"), f"{where}: unterminated expression ends {text[-60:]!r}"
