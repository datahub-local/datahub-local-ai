# Design

## Context

Read off the export, the config and issue #109's measurements.

- `curator_config.json` had `lookback_days: 5`, one `category_weights` map and no source typing.
- `content_feed_curator.workflow.json`'s `fetch_candidates` queried Miniflux once per category with
  `published_after = now - lookback_days`, and every entry became a candidate regardless of who
  wrote it.
- Seattle Data Guy's newest item was 2026-10-15, 13 days before the ticket; a 5-day window gives him
  zero candidates every run.
- `filter_stats.per_source` counted fetched items per source but carried no drop reason, and the
  digest printed only aggregates, so "why is this source absent" was an investigation.
- Hacker News arrives as a separate source with votes; it is not a publisher and must not be
  counted as a company in the balance.

## Decisions

### D1. The axis is explicit, per feed, and defaulted conservatively

`reference_people` names a feed host, a person and a category. A feed that is not listed is a
company. That default is deliberate: a newly subscribed vendor feed keeps the short window rather
than being treated as a slow writer and admitted stale. The feed list itself remains
`datahub-local-core`'s; this file only classifies it, so the two cannot disagree about what is
subscribed. A platform profile shares its host with every other feed on the platform, so an entry
may also name the feed URL; the URL is then the identity and the host alone still reads as a
company, which keeps one platform from turning every feed on it into one person.

### D2. Cadence is a window, not a special case

A person's post is admitted by age, with a wider allowance, and `recency` still costs it in the
pre-rank. The rejected alternative was "latest N items per person regardless of age": it hides how
old the post is and lets a dormant feed dominate with year-old writing. A declared window keeps the
age honest and makes the trade visible.

### D3. One query, filtered locally by kind

Miniflux is queried with the wider window so a person's entry is present at all, then
`fetch_candidates` drops a company entry older than `lookback_days`. The rejected alternative was two
queries per category, which doubles the request count and still needs the same local filter for the
overlap. The local filter is the part that guarantees a vendor cannot ride in on the wider window.

### D4. The pool floor is enforced; the backlog target is reported

The pool is where a monthly writer loses to vendor frequency, so
`min_person_share_pool` reserves slots before category quotas are allocated. Admission is where
quality is decided by the judge, so `min_person_share_backlog` is a target the digest reports and
warns about, never a reason to admit a row the judge rejected. Enforcing both would make the mix
outrank postability, which is the defect this change is meant to remove rather than move.

### D5. The per-source record is one object carried through every stage

`per_feed` is seeded in `fetch_candidates` (including a record for a reference person the instance
does not subscribe, reason `not subscribed`), carried by `filter_candidates`, `rank_candidates`,
`pick_finalists` and `admit_to_backlog`, each bumping its own counters. `build_digest` is the only
reader. One object rather than a report per node means a source's whole path is readable in one
place, and a stage that is added later has an obvious place to add its counter.

### D6. "Absent" means no admitted row

The digest lists a reference person when the run admitted no row from them, not only when they got
no pool slot. A person cut by the judge is just as missing from the reader's view, and the stage name
is what makes the report actionable. Companies are summarised so a quiet vendor cannot bury the
person list.

### D7. Hacker News is `community`

It is neither a company nor a person, and counting it as either would distort the share it is
supposed to measure. `community` counts for neither side of the target.

## Risks

- **The wider window admits more entries per person.** Bounded by the same
  `max_entries_per_category` and by the kind filter; the person list is 33 feeds, so the added
  volume is small against a 1000-entry cap.
- **A mis-typed feed host silently classifies a person as a company.** The digest names a reference
  person with `not subscribed` when the host does not match a subscribed feed, which is the visible
  symptom; the test pins the host of the motivating example.
- **A 30-day window can surface an old post.** Accepted: recency still costs it at pre-rank and the
  row's `PUBLISHED_AT` carries the real date, so the publisher can still skip it on the hook's TTL.

## Open Questions

- Which surface is "the post feed" — answered in `docs/agent/n8n.md` as the `content_queue` post
  lane.
- Whether the live Miniflux instance subscribes every reference person is not answerable from this
  repository. It is `[UNVERIFIED]` here and the run's per-feed report answers it on the next
  execution.

## Definition of Done

- The config names the reference people, the person window and both balance values.
- The curator classifies each candidate, applies the per-kind window and reserves the pool floor.
- The digest names a reference person with no admitted row and the stage, and reports the admitted
  mix per category.
- `uv run -- pytest agents/n8n/scripts/ -q` and `openspec validate --all` pass.
