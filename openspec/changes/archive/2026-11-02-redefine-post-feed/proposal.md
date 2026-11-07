# Proposal

## Why

The post feed selects companies far more often than the practitioners a reader follows, and the
clearest case is arithmetic rather than judgement: Seattle Data Guy's newest item was
**2026-10-15**, 13 days before issue #109 was written, against `lookback_days = 5`. The curator
runs daily, so he contributed **zero candidates on every run** while a vendor publishing 1-3 times
a week always cleared the window. Nothing in the digest named him, because the run reports only
aggregate counts.

The feed has one untyped axis today: `category_weights` per topic, and every Miniflux feed is a
company to every stage. A monthly essayist and a vendor blog are indistinguishable until the
pre-rank, where the vendor's publishing frequency, benchmark numbers and Hacker News votes win the
pool slot. The mix that reaches the reader is therefore whatever frequency produced, not an intent
that can fail loudly.

## What Changes

- **A source-kind axis.** `agents/n8n/datasets/curator_config.json` gains `reference_people`, one
  entry per person with a feed host and a category. Every other Miniflux feed is a company; Hacker
  News is a third kind, `community`, because it is neither.
- **A per-kind cadence window.** Companies keep `lookback_days` (5). Reference people get
  `person_lookback_days` (30). The Miniflux query is widened to the larger window and each entry is
  filtered locally by its own kind, so a vendor entry cannot ride in on a person's window. Recency
  still costs the older post at pre-rank: it is admitted as older, not passed off as fresh.
- **A stated balance.** `balance.min_person_share_pool` (0.35) reserves that share of
  `max_candidates` for reference people before category quotas are filled.
  `balance.min_person_share_backlog` (0.35) is reported against the queue and warns, but does not
  force an admission the judge rejected.
- **A per-source report on every run.** `fetch_candidates` seeds one `per_feed` record per
  subscribed feed and per missing reference person; fetch, filter, pool, judge and admission add
  their counters to it; `build_digest` prints one line per reference person with no admitted row
  and the stage that stopped it, plus the admitted mix per category.
- **The feed definition is written down** — target topics, source kinds, and the company-vs-person
  balance — in `docs/agent/n8n.md`, and the config's own comments name Seattle Data Guy's
  arithmetic.

## Capabilities

### Added Capabilities

- `post-feed`: the definition of the post lane's feed, the source-kind axis and its cadence windows,
  the balance floor and target, and the per-source report that answers why a source is absent.

## Impact

- `agents/n8n/datasets/curator_config.json` — `reference_people`, `person_lookback_days`, `balance`.
- `agents/n8n/workflows/content_feed_curator.workflow.json` — `parse_curator_config`,
  `fetch_candidates`, `filter_candidates`, `rank_candidates`, `pick_finalists`,
  `admit_to_backlog`, `build_digest`, in both graph copies.
- `agents/n8n/scripts/test_post_feed_mix.py` — the new offline test.
- `docs/agent/n8n.md` — the written post-feed definition.
- `datahub-local-core` — no change: its `miniflux_config.json` already subscribes the reference
  people and the feed list is not duplicated here. Whether the live instance carries the row is read
  from the run's own report.

## Non-goals

- **No new subscription.** The feed list stays in `datahub-local-core`; this change names which
  feeds are people, it does not add feeds.
- **No judge change.** `curator_judge.md` is already publisher-neutral; company dominance happens
  upstream of it.
- **No enforced person quota at admission.** The judge's postability floor stays the only admission
  gate; forcing a rejected row into the queue would trade the mix for quality.
- **No blog-lane or public-page change.** This is the `content_queue` post lane only.
