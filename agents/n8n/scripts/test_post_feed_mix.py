"""The post feed's source-kind axis, cadence window, balance floor and per-source report.

Offline: reads the committed export and config, and executes the Code nodes whose
decisions are invisible in the graph. The Miniflux API is stubbed at the HTTP boundary
so the person window and the per-feed report are exercised as code, not asserted from a
config value.
"""

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parents[1]
WORKFLOWS = AGENTS / "workflows"
CURATOR = json.loads((WORKFLOWS / "content_feed_curator.workflow.json").read_text())
CFG = json.loads((AGENTS / "datasets" / "curator_config.json").read_text())

NODE_REQUIRED = "node is required to execute a Code node's decisions"

RUNNER = r"""
async function __n8n_main__() {
  const stubs = JSON.parse(process.env.STUBS || '{}');
  const $ = (name) => {
    const items = (stubs.nodes && stubs.nodes[name]) || [];
    return {
      first: () => ({ json: items[0] || {} }),
      all: () => items.map((j) => ({ json: j })),
      item: { json: items[0] || {} },
    };
  };
  const $input = { all: () => ((stubs.input || []).map((j) => ({ json: j }))) };
  // n8n binds $json to the current item; a Code node reading one input item reads the first.
  const $json = (stubs.input || [])[0] || {};
  const $execution = { id: stubs.execution_id || '1' };
  const $env = stubs.env || {};
  const console = { log: () => {}, warn: () => {}, error: () => {} };
  const ctx = {
    helpers: {
      httpRequest: async (opts) => {
        const method = opts.method || 'GET';
        const hit = (stubs.http || []).find(
          (h) =>
            (h.method || 'GET') === method &&
            String(opts.url || '').startsWith(h.url) &&
            (h.category_id === undefined || String((opts.qs || {}).category_id) === String(h.category_id))
        );
        if (!hit) throw new Error('unexpected http: ' + method + ' ' + opts.url + ' ' + JSON.stringify(opts.qs || {}));
        return hit.response;
      },
    },
  };
  const __result = await (async function () {
__CODE__
  }).call(ctx);
  process.stdout.write(JSON.stringify(__result));
}
__n8n_main__().catch((e) => { process.stderr.write(String((e && e.stack) || e)); process.exit(1); });
"""


def _node(name):
    return next(n for n in CURATOR["nodes"] if n["name"] == name)


def _js(name):
    return _node(name)["parameters"]["jsCode"]


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def _run(code, nodes=None, input_=None, env=None, http=None):
    src = RUNNER.replace("__CODE__", code)
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as fh:
        fh.write(src)
        path = fh.name
    payload = {
        "nodes": nodes or {},
        "input": input_ or [],
        "env": env or {},
        "http": http or [],
    }
    try:
        done = subprocess.run(
            ["node", path],
            capture_output=True,
            text=True,
            env=dict(os.environ, STUBS=json.dumps(payload)),
            check=False,
        )
    finally:
        Path(path).unlink()
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _items(result):
    return [item["json"] for item in result]


def _config(**overrides):
    base = {
        "lookback_days": 5,
        "person_lookback_days": 30,
        "reference_people": [
            {"name": "Slow Person", "feed": "slow.example.com", "category": "Data"},
            {"name": "Missing Person", "feed": "missing.example.com", "category": "Data"},
        ],
        "max_candidates": 4,
        "max_per_host": 3,
        "category_weights": {"Data": 1.0, "default": 0.0},
        "category_keywords": {"Data": ["data"]},
        "exclude_categories": ["News", "Tech"],
        "title_blocklist": ["newsletter"],
        "domain_blocklist": [],
        "aggregator_hosts": [],
        "shared_keywords": [],
        "sources": {"hn_top": {"enabled": False}},
        "balance": {"min_person_share_pool": 0.5, "min_person_share_backlog": 0.5},
    }
    base.update(overrides)
    return base


def _parsed(cfg):
    return _items(_run(_js("parse_curator_config"), input_=[{"output": json.dumps(cfg)}]))[0]


def _miniflux_http(category_id=1):
    old = "2026-10-20T12:00:00.000Z"
    fresh = "2026-11-01T12:00:00.000Z"
    return [
        {"url": "http://miniflux.local/v1/categories", "response": [{"id": category_id, "title": "Data"}]},
        {
            "url": "http://miniflux.local/v1/feeds",
            "response": [
                {
                    "id": 1,
                    "feed_url": "https://slow.example.com/feed",
                    "title": "Slow Person",
                    "category": {"id": category_id, "title": "Data"},
                },
                {
                    "id": 2,
                    "feed_url": "https://vendor.example.com/feed",
                    "title": "Vendor",
                    "category": {"id": category_id, "title": "Data"},
                },
            ],
        },
        {
            "url": "http://miniflux.local/v1/entries",
            "category_id": category_id,
            "response": {
                "total": 3,
                "entries": [
                    {
                        "id": 11,
                        "url": "https://slow.example.com/a",
                        "title": "A data essay from a slow writer",
                        "published_at": old,
                        "content": "<p>data data data</p>",
                        "feed": {
                            "id": 1,
                            "feed_url": "https://slow.example.com/feed",
                            "title": "Slow Person",
                            "category": {"id": category_id, "title": "Data"},
                        },
                    },
                    {
                        "id": 12,
                        "url": "https://vendor.example.com/a",
                        "title": "Vendor ships a data feature",
                        "published_at": fresh,
                        "content": "<p>data 42% faster</p>",
                        "feed": {
                            "id": 2,
                            "feed_url": "https://vendor.example.com/feed",
                            "title": "Vendor",
                            "category": {"id": category_id, "title": "Data"},
                        },
                    },
                    {
                        "id": 13,
                        "url": "https://vendor.example.com/b",
                        "title": "Vendor data post from last week",
                        "published_at": old,
                        "content": "<p>data 10% faster</p>",
                        "feed": {
                            "id": 2,
                            "feed_url": "https://vendor.example.com/feed",
                            "title": "Vendor",
                            "category": {"id": category_id, "title": "Data"},
                        },
                    },
                ],
            },
        },
    ]


def test_the_config_names_reference_people_per_category():
    people = CFG["reference_people"]
    names = {p["name"] for p in people}
    assert "Seattle Data Guy" in names
    categories = {p["category"] for p in people}
    assert categories == {"Data", "AI", "DevOps"}
    assert CFG["person_lookback_days"] > CFG["lookback_days"]
    assert CFG["balance"]["min_person_share_pool"] > 0


def test_parse_curator_config_turns_the_reference_list_into_a_person_window():
    out = _parsed(_config())
    assert out["person_lookback_days"] == 30
    assert out["max_lookback_days"] == 30
    assert "slow.example.com" in out["person_feeds"]
    assert out["balance"]["min_person_share_pool"] == 0.5
    # The intake query is the wider of the two windows, not the company window.
    run_at = datetime.fromisoformat(out["run_at"].replace("Z", "+00:00"))
    published = datetime.fromtimestamp(out["published_after"], tz=timezone.utc)
    assert 29.9 < (run_at - published).total_seconds() / 86400 < 30.1


def test_a_person_entry_outside_the_company_window_is_still_a_candidate():
    parsed = _parsed(_config())
    items = _items(
        _run(
            _js("fetch_candidates"),
            nodes={"parse_curator_config": [parsed]},
            env={
                "MINIFLUX_URL": "http://miniflux.local",
                "MINIFLUX_API_USER": "u",
                "MINIFLUX_API_PASSWORD": "p",
            },
            http=_miniflux_http(),
        )
    )
    urls = {i["url"] for i in items}
    assert "https://slow.example.com/a" in urls
    assert "https://vendor.example.com/a" in urls
    assert "https://vendor.example.com/b" not in urls
    stats = items[0]["_fetch_stats"]
    assert stats["per_feed"]["slow.example.com"]["in_window"] == 1
    assert stats["per_feed"]["vendor.example.com"]["out_of_window"] == 1
    assert stats["per_feed"]["missing.example.com"]["absent_reason"] == "not subscribed"


def test_a_blocklisted_title_is_attributed_to_its_feed():
    parsed = _parsed(_config())
    base = {
        "canonical_url": "slow.example.com/a",
        "host": "slow.example.com",
        "feed_host": "slow.example.com",
        "source_key": "slow.example.com",
        "source_kind": "person",
        "source_name": "Slow Person",
        "feed_title": "Slow Person",
        "category": "Data",
        "title": "Newsletter: the week in data",
        "excerpt": "data",
        "content_text": "data",
        "word_count": 200,
        "thin_content": False,
        "hours_old": 24,
        "starred": False,
        "votes": 0,
        "comments": 0,
        "source": "miniflux",
    }
    good = {
        **base,
        "url": "https://vendor.example.com/a",
        "canonical_url": "vendor.example.com/a",
        "host": "vendor.example.com",
        "feed_host": "vendor.example.com",
        "source_key": "vendor.example.com",
        "source_kind": "company",
        "source_name": "Vendor",
        "feed_title": "Vendor",
        "title": "A vendor data post",
    }
    fetch_stats = {"per_source": {"miniflux": 2}, "per_feed": {}, "source_errors": [], "total": 2}
    kept = _items(
        _run(
            _js("filter_candidates"),
            nodes={
                "parse_curator_config": [parsed],
                "read_legacy_sheet": [],
                "read_articles_sheet": [],
                "fetch_candidates": [
                    {**base, "url": "https://slow.example.com/a", "_fetch_stats": fetch_stats},
                    {**good, "_fetch_stats": fetch_stats},
                ],
            },
        )
    )
    assert len(kept) == 1
    assert kept[0]["url"] == "https://vendor.example.com/a"
    assert kept[0]["_filter_stats"]["per_feed"]["slow.example.com"]["blocked"] == 1


def test_the_pool_keeps_a_person_when_company_candidates_rank_higher():
    parsed = _parsed(_config(max_candidates=4))
    person = {
        "url": "https://slow.example.com/a",
        "canonical_url": "slow.example.com/a",
        "host": "slow.example.com",
        "feed_host": "slow.example.com",
        "source_key": "slow.example.com",
        "source_kind": "person",
        "source_name": "Slow Person",
        "feed_title": "Slow Person",
        "category": "Data",
        "title": "A data essay without a number",
        "excerpt": "data",
        "content_text": "data",
        "word_count": 200,
        "thin_content": False,
        "hours_old": 13 * 24,
        "starred": False,
        "votes": 0,
        "comments": 0,
        "source": "miniflux",
    }
    titles = [
        "Vendor ships a 42% faster query engine",
        "Vendor launches a streaming cache with 10x throughput",
        "Vendor cuts storage costs by 30%",
        "Vendor adds real-time ingestion to its platform",
    ]
    companies = []
    for n, title in enumerate(titles):
        companies.append(
            {
                **person,
                "url": f"https://vendor{n}.example.com/a",
                "canonical_url": f"vendor{n}.example.com/a",
                "host": f"vendor{n}.example.com",
                "feed_host": f"vendor{n}.example.com",
                "source_key": f"vendor{n}.example.com",
                "source_kind": "company",
                "source_name": f"Vendor {n}",
                "feed_title": f"Vendor {n}",
                "title": title,
                "hours_old": 1,
                "votes": 200,
                "comments": 20,
            }
        )
    fetch_stats = {"per_source": {"miniflux": 5}, "per_feed": {}, "source_errors": [], "total": 5}
    kept = _items(
        _run(
            _js("filter_candidates"),
            nodes={
                "parse_curator_config": [parsed],
                "read_legacy_sheet": [],
                "read_articles_sheet": [],
                "fetch_candidates": [
                    {**person, "_fetch_stats": fetch_stats},
                    *[{**c, "_fetch_stats": fetch_stats} for c in companies],
                ],
            },
        )
    )
    assert len(kept) == 5
    ranked = _items(
        _run(_js("rank_candidates"), nodes={"parse_curator_config": [parsed]}, input_=kept)
    )
    urls = {r["url"] for r in ranked}
    assert "https://slow.example.com/a" in urls
    stats = ranked[0]["filter_stats"]
    assert stats["people_pool"] >= 1
    assert stats["people_floor"] == 2
    assert stats["people_floor_met"] is False


def test_admission_reports_the_mix_by_kind():
    parsed = _parsed(_config())
    person = {
        "cid": "c1",
        "url": "https://slow.example.com/a",
        "title": "A data essay",
        "host": "slow.example.com",
        "source_key": "slow.example.com",
        "source_kind": "person",
        "source_name": "Slow Person",
        "category": "Data",
        "judged": True,
        "judge_blocked": False,
        "postability": 8,
        "hours_old": 24,
        "published_at": "2026-11-01T12:00:00.000Z",
    }
    company = {
        **person,
        "cid": "c2",
        "url": "https://vendor.example.com/a",
        "title": "A vendor data post",
        "host": "vendor.example.com",
        "source_key": "vendor.example.com",
        "source_kind": "company",
        "source_name": "Vendor",
    }
    pick_stats = {
        "per_feed": {
            "slow.example.com": {"name": "Slow Person", "kind": "person", "pool": 1, "finalists": 1},
            "vendor.example.com": {"name": "Vendor", "kind": "company", "pool": 1, "finalists": 1},
        },
        "people_pool": 1,
        "company_pool": 1,
        "people_floor": 1,
        "people_floor_met": True,
        "person_share_target": 0.5,
        "considered": 2,
        "finalists": 2,
        "people_finalists": 1,
    }
    rows = _items(
        _run(
            _js("admit_to_backlog"),
            nodes={
                "parse_curator_config": [parsed],
                "read_articles_sheet": [],
                "pick_finalists": [{"_stats": pick_stats}],
            },
            input_=[person, company],
        )
    )
    assert len(rows) == 2
    stats = rows[0]["_stats"]
    assert stats["admitted_by_kind"]["person"] == 1
    assert stats["admitted_by_kind"]["company"] == 1
    assert stats["person_share_admitted"] == 0.5
    assert stats["per_feed"]["slow.example.com"]["admitted"] == 1


def test_the_digest_names_an_absent_person_and_the_stage():
    stats = {
        "considered": 4,
        "people_pool": 1,
        "company_pool": 3,
        "people_floor": 2,
        "people_floor_met": False,
        "person_share_target": 0.5,
        "finalists": 1,
        "people_finalists": 0,
        "admitted": 1,
        "admitted_by_kind": {"person": 0, "company": 1, "community": 0},
        "admitted_by_category_kind": {"Data": {"person": 0, "company": 1, "community": 0}},
        "backlog_by_kind": {"person": 0, "company": 1},
        "person_share_backlog": 0,
        "person_backlog_target": 0.5,
        "person_share_admitted": 0,
        "person_mix_short": True,
        "per_feed": {
            "seattledataguy.substack.com": {
                "name": "Seattle Data Guy",
                "kind": "person",
                "fetched": 0,
                "in_window": 0,
                "pool": 0,
                "absent_reason": "no items in window",
            },
            "benn.substack.com": {
                "name": "Benn Stancil",
                "kind": "person",
                "fetched": 2,
                "in_window": 2,
                "kept": 2,
                "pool": 1,
                "finalists": 0,
            },
        },
    }
    out = _items(
        _run(
            _js("build_digest"),
            input_=[
                {
                    "rank": 1,
                    "TITLE": "A vendor data post",
                    "URL": "https://vendor.example.com/a",
                    "SOURCE": "vendor.example.com",
                    "TOPIC": "Data",
                    "SCORE": 0.8,
                    "PRIORITY": "VERY_HIGH",
                    "postability": 8,
                    "features": {},
                    "_stats": stats,
                }
            ],
        )
    )[0]
    text = out["digest_text"]
    assert "Seattle Data Guy: no items in window" in text
    assert "Benn Stancil: below the judge cut" in text
    assert "mix  pool people 1/4" in text
    assert "mix by category  Data people 0 / company 1" in text
