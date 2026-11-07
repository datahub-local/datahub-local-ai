# Proposal

## Why

The article review gate judged every draft against the entry's seed page only. The writer is
allowed to fetch up to three more pages during a draft, and the spec requires it to cite the pages
it read. A draft grounded in a fetched page was therefore rejected as "facts not in the Source
Material", the retry could not converge, and the entry ended `MAX_RETRIES_EXCEEDED`.

Row 3 on 2026-11-07 (execution 16033) is the live case. The writer fetched `docs/index.md` and
`docs/concepts/ensembles.md`; the ledger verified three quoted blocks from them. The draft used
the Ensembles page's platform-team roster, its 30m/5m/weekdays-9am schedules and its `authRefs`
patch. Every review turn rejected those as absent from the seed page, which was the docs home
page, and the fourth draft exhausted the bound.

## What Changes

- **The fact check accepts a fetched page.** The review prompt's fact rule now reads the entry's
  inputs, the seed page and every page the writer fetched during the run. A fact from a fetched
  page is sourced even when the seed page does not carry it; a fact absent from all of them, or a
  citation of a page the writer did not fetch, remains a failure.
- **The Source Material block says what it is.** It is the entry's seed page, not the whole
  corpus. The writer's fetched pages are in the same session's earlier turns and the ledger names
  them, and the prompt points the reviewer at both.
- **The lane's docs record the rule and the failure that named it.**

## Capabilities

`content-writer`.

## Out of scope

- No change to the research bound, the ledger verification or the code checks.
- No change to the aspect or improve turns; they do not judge facts.
- The live row is not requeued here. The entry stays `ERROR` until a person puts it back to
  `QUEUE`, after the image with the new prompt is live.
