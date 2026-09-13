---
name: design-spec
description: Generate a design spec file under docs/specs/ for an AI/data project (dbt or dlt pipeline, semantic layer, MCP tooling, Airflow DAG, Superset dashboard, Sympozium or n8n agent work), following this repo's numbering, verification and structure conventions. Use when the user asks to write, draft, extend or revise a design spec. Review-driven: every phase ends at a mandatory user checkpoint; never produce a full spec without feedback between phases.
---

# Design spec authoring

Produce a **decision record**, not a plan that gets deleted when done. The
user's review is part of the workflow, not an interruption: each phase below
ends at a checkpoint where you stop and wait for explicit feedback.

Canonical conventions: `CLAUDE.md` → "Design specs (`docs/specs/`)".
Fullest example on disk: `docs/specs/003-data-quality-and-lineage.md`.

## Checkpoint rules — apply to every phase

1. Present the phase output, then stop and ask for review. Never continue past
   a checkpoint without an explicit user answer.
2. Apply feedback, re-present only what changed, and ask again.
3. Record every decision the feedback produced **in the spec itself** — under
   "Alternatives considered" or inline where it lands. Rationale lives where the
   next reader looks, not in chat.
4. If feedback contradicts a verified finding, re-verify; if the finding holds,
   say so and let the user decide. The user decides scope; the repo decides facts.
5. Never commit. Suggest one `docs(spec): ...` line only when asked.

## Phase 1 — Intake → checkpoint

Ask, do not assume, until you can state:

- The project or change in one sentence, and why now.
- Which repos/sub-projects it touches (`workflows/dbt|dlt|airflow|superset`,
  `agents/sympozium|n8n`, datahub-local-core, datahub-local-ai-mcp).
- Hard constraints: footprint bars, no new stateful services, existing alert
  path only, bronze-is-not-a-consumer-layer, the AI prompt policy, no committed
  generated copies.
- What "done" looks like operationally.

**Checkpoint:** the user confirms scope and constraints before any research.

## Phase 2 — Numbering and placement → checkpoint

1. List `docs/specs/`. Filenames are numbered by disk position: the next top
   number is max + 1.
2. A spec that *extends* an existing one (adds a phase, revisits a decision)
   takes a sub-number under its parent (`002-03-...`), not a new top number.
3. The filename number is not the number prose uses — prose carries the logical
   order. Read the opening blockquote of every sibling to see which number each
   file claims, then pick the next logical number consistently.
4. Propose `NNN-kebab-case-title.md` plus the opening blockquote: every sibling
   named by relative link (`[002-01-semantic-layer.md](002-01-semantic-layer.md)`),
   which number this file is in each scheme, and a `**Numbering:**` line.

**Checkpoint:** the user approves filename and numbering.

## Phase 3 — Gates and verification → checkpoint

Settle the unknowns that could change the plan before the spec is allowed one.

- List them: does the adapter/package support X at the pinned version, does the
  metric exist, is the image multi-arch, how many rows/models/objects are there.
- Verify against the running system and the repository, never inference: read
  source at the pinned tag, query the Prometheus metadata API, `kubectl get`,
  count files. A wrong name fails silently — the spec must not carry one.
- Every claim cites its source (URL, `file:line`, command run).
- Anything unverifiable is marked `[UNVERIFIED]` — in place beats dropping the
  fact or asserting it — and names the task that settles it.
- A passed gate still records the fallback it did not take, so the reasoning is
  not re-derived later.

**Checkpoint:** present the gate table (unknown | finding | source |
consequence). The user knows this homelab and may close `[UNVERIFIED]` items or
add unknowns you missed.

## Phase 4 — Outline and goals → checkpoint

Propose the section skeleton and draft the goals table now; everything downstream
hangs off the acceptance signals.

| # | Goal | Acceptance signal |

- Signals are observable and testable ("`get_model_health` returns a state for
  every model backing a registry metric"), never aspirational ("improve quality").
- Non-goals are mandatory: state what the spec explicitly does not deliver and
  where the line comes from (OSS vs paid, footprint, single operator).

**Checkpoint:** the user approves skeleton, goals and non-goals.

## Phase 5 — Draft in passes → checkpoints

Write the file in this order, pausing for review at the marked breaks:

0. **Gate findings — read first** (only when the spec had blocking unknowns):
   evidence first, because the plan makes sense only once these are known.
1. **Context** — where the platform is today, counted not remembered; the
   problem in descending order of cost; why the pieces ship together; where this
   must not create a second source of truth.
2. **Goals** and non-goals.  ⟵ *pause: context + goals reviewed*
3. **Architecture** — mermaid diagram plus a layer-responsibility table
   (Layer | Component | Owns | Must not); name the trust boundary and which
   layer is untrusted.
4. **Design** — the actual decisions, each with the alternative it rejected and
   why. Data model, agent/tool interface, quality or eval strategy,
   observability, hosting — whichever apply.
5. **Implementation plan** — phases of PR-sized checkbox tasks with stable ids
   prefixed per repo (`WF-*` workflows, `INFRA-*` core, `AI-*` agents/MCP),
   cross-repo *Blocked by* links, and a **Done when:** per phase tied back to a
   goal. Add the cross-repo sequencing table and the ordering mistake most
   likely to waste a weekend.  ⟵ *pause: design + plan reviewed*
6. **Risks** (Risk | Mitigation), **Open questions** — each with a **Settle
   by:** — and a **Definition of done** referencing the goals, ending with the
   one check that sums the whole spec when one exists.  ⟵ *pause: full draft*

While drafting:

- Keep rejected alternatives and gate findings; mark tasks `[x]` as they land,
  never delete them.
- Prompts follow the AI prompt policy: short, literal, action-oriented, in
  files — reference the file, never inline a tutorial.
- No second source of truth: if the design stores something the dbt manifest,
  the semantic registry or the warehouse already owns, resolve it structurally
  and say which store wins.
- Nothing user-facing reads bronze; datasets and semantic models reference
  silver/gold only.
- Absence must be expressible: tool results and report formats carry
  `unknown`/`unavailable` as first-class values, never a mandatory field a
  model will fill with the nearest number.
- Prefer render-time templates over committed generated artifacts; only add a
  build step when the artifact genuinely cannot be templated (e.g. a binary zip).

## Phase 6 — Final checks → checkpoint

Verify mechanically before declaring done:

- [ ] Opening blockquote links every sibling by relative path and states both
      numbering schemes; the set stays consistent with the files it names.
- [ ] `rg -n 'docs/specs' --glob '!docs/specs/**'` — code points at spec paths
      (e.g. the comment in `workflows/dbt/semantic/bodega.yaml`); update any
      path this spec renames or renumbers.
- [ ] Every task id is unique and its prefix maps to a real repo.
- [ ] Every `[UNVERIFIED]` names the task that settles it.
- [ ] Every goal row has an acceptance signal; the definition of done
      references the goals.
- [ ] `grep -nP '^\s+.*[^\x00-\x7F]' <spec>` — ASCII-only inside indented
      blocks; invalid UTF-8 has broken agent `status.result` before.
- [ ] One top-to-bottom read for the two failure modes: a fact asserted without
      a source, and a mandatory format with no way to express absence.

**Checkpoint:** the user gives final approval. If they then ask to commit,
suggest one line: `docs(spec): add NNN <title>`.
