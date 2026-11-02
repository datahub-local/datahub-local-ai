# Tasks

## 1. The source-kind axis

- [x] 1.1 `datasets/curator_config.json`: add `reference_people` (name, feed host, category),
  including Seattle Data Guy under Data.
- [x] 1.2 `datasets/curator_config.json`: add `person_lookback_days: 30` and `balance` with
  `min_person_share_pool` and `min_person_share_backlog` at 0.35.
- [x] 1.3 `parse_curator_config`: parse the person list, the person window and the balance, derive
  `person_feeds` and `max_lookback_days`, and widen `published_after`.
- [x] 1.4 `fetch_candidates`: tag each Miniflux entry `person` or `company` by feed host, apply the
  per-kind window locally, tag Hacker News `community`, and apply the company window to it locally
  because the widened intake query is not its window.
- [x] 1.5 `parse_curator_config` and `fetch_candidates`: match a platform profile by its optional
  `feed_url`, so a shared host cannot make every feed on the platform one person.

## 2. The balance

- [x] 2.1 `rank_candidates`: fill the person pool floor before category quotas and record
  `people_pool`, `people_floor`, `people_floor_met` and `person_share_target`.
- [x] 2.2 `admit_to_backlog`: compute admitted and backlog shares by kind and per category, and warn
  when the admitted or backlog share is under target without changing admission.

## 3. The per-source report

- [x] 3.1 `fetch_candidates`: seed one `per_feed` record per subscribed feed and per missing
  reference person, with `fetched`, `in_window`, `out_of_window` and `absent_reason`.
- [x] 3.2 `filter_candidates`, `rank_candidates`, `pick_finalists`, `admit_to_backlog`: carry
  `per_feed` and add their own drop counters.
- [x] 3.3 `build_digest`: print one line per reference person with no admitted row and the stage,
  a company summary, and the admitted mix per category.

## 4. Proof

- [x] 4.1 `scripts/test_post_feed_mix.py`: the config names the people, the person window admits an
  older person entry and not an older company entry, the community window drops an older Hacker News
  story, a platform person is matched by feed URL not host, a blocklisted title is attributed to its
  feed, the pool keeps a person against higher-ranked companies, admission reports the mix without a
  community row diluting it, and the digest names an absent person and its stage.
- [x] 4.2 `uv run -- pytest agents/n8n/scripts/ -q` passes.
- [x] 4.3 `openspec validate --all` passes.

## 5. Documentation

- [x] 5.1 `docs/agent/n8n.md`: write the post-feed definition, the cadence windows, Seattle Data
  Guy's arithmetic and the per-source report.
