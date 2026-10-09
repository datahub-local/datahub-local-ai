"""Tests for --create in apply_workflow_changes.py.

The network is faked, so these run anywhere. They pin the idempotency the
create path promises: a body is POSTed once, and a name that already exists
live is left untouched.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("apply_workflow_changes.py")
_spec = importlib.util.spec_from_file_location("apply_workflow_changes", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


class FakeApi:
    def __init__(self, existing=None):
        self.store = {w["id"]: dict(w) for w in (existing or [])}
        self.calls = []

    def __call__(self, url, key, path, method="GET", body=None):
        self.calls.append((method, path, body))
        if method == "GET" and path.startswith("/api/v1/workflows?"):
            return {"data": [{"id": w["id"], "name": w["name"]} for w in self.store.values()]}
        if method == "POST" and path.endswith("/activate"):
            self.store[path.split("/")[-2]]["active"] = True
            return {}
        if method == "PUT":
            self.store[path.rsplit("/", 1)[1]].update(body)
            return {}
        if method == "POST":
            wid = f"new{len(self.store) + 1}"
            self.store[wid] = {"id": wid, "active": False, **body}
            return {"id": wid}
        if method == "GET" and path.startswith("/api/v1/workflows/"):
            return self.store[path.rsplit("/", 1)[1]]
        raise AssertionError(f"unexpected {method} {path}")


BODY = {
    "name": "Visual Studio",
    "nodes": [
        {
            "name": "start",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [0, 0],
            "parameters": {},
        }
    ],
    "connections": {},
    "settings": {"errorWorkflow": "err"},
}


def test_creates_when_absent(monkeypatch, capsys):
    fake = FakeApi()
    monkeypatch.setattr(mod, "api", fake)

    mod.create_workflow("u", "k", BODY, do_write=True)

    assert "created id=" in capsys.readouterr().out
    assert len(fake.store) == 1
    posted = [c for c in fake.calls if c[0] == "POST"]
    assert posted and posted[0][2]["name"] == "Visual Studio"
    assert posted[0][2]["settings"] == {"errorWorkflow": "err"}


def test_existing_name_left_untouched(monkeypatch, capsys):
    fake = FakeApi(
        existing=[
            {"id": "abc", "name": "Visual Studio", "nodes": [], "connections": {}, "settings": {}}
        ]
    )
    monkeypatch.setattr(mod, "api", fake)

    mod.create_workflow("u", "k", BODY, do_write=True)

    assert "already exists" in capsys.readouterr().out
    assert not [c for c in fake.calls if c[0] == "POST"]
    assert fake.store["abc"]["nodes"] == []


def test_dry_run_does_not_write(monkeypatch, capsys):
    fake = FakeApi()
    monkeypatch.setattr(mod, "api", fake)

    mod.create_workflow("u", "k", BODY, do_write=False)

    assert "dry run" in capsys.readouterr().out
    assert fake.store == {}


def test_body_needs_name():
    with pytest.raises(SystemExit):
        mod.create_workflow("u", "k", {"nodes": [1]}, do_write=False)


def test_body_needs_nodes():
    with pytest.raises(SystemExit):
        mod.create_workflow("u", "k", {"name": "x"}, do_write=False)


def _live(nodes, connections):
    return {
        "id": "wf1",
        "name": "Curator",
        "active": True,
        "nodes": nodes,
        "connections": connections,
        "settings": {},
    }


def _n(name):
    return {"name": name, "type": "t", "typeVersion": 1, "position": [0, 0], "parameters": {}}


def test_typed_connections_set_a_non_main_type(monkeypatch):
    """A sub-node attaches over ai_languageModel, not main; a dict spec reaches it."""
    fake = FakeApi(existing=[_live(
        [_n("ai_model"), _n("judge_llm"), _n("judge_llm_backfill")],
        {"ai_model": {"ai_languageModel": [[{"node": "judge_llm", "type": "ai_languageModel", "index": 0}]]}},
    )])
    monkeypatch.setattr(mod, "api", fake)

    spec = {"workflow": "wf1", "connections": {"ai_model": {"ai_languageModel": [[
        {"node": "judge_llm", "type": "ai_languageModel", "index": 0},
        {"node": "judge_llm_backfill", "type": "ai_languageModel", "index": 0},
    ]]}}}
    mod.process("u", "k", spec, do_apply=True)

    got = fake.store["wf1"]["connections"]["ai_model"]["ai_languageModel"][0]
    assert [o["node"] for o in got] == ["judge_llm", "judge_llm_backfill"]


def test_a_list_connection_spec_still_means_main(monkeypatch):
    fake = FakeApi(existing=[_live([_n("a"), _n("b")], {"a": {"main": [[{"node": "b", "type": "main", "index": 0}]]}})])
    monkeypatch.setattr(mod, "api", fake)

    spec = {"workflow": "wf1", "connections": {"a": []}}
    mod.process("u", "k", spec, do_apply=True)
    assert fake.store["wf1"]["connections"]["a"]["main"] == []
