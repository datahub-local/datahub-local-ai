# Design

## Context

See [proposal.md](proposal.md) — Why. The facts behind the approach, read from the
live database, the exports and the API:

- **The artifact is a base64 data URL in workflow JSON.** `agent_result` builds
  `IMAGE: 'data:' + mime + ';base64,' + buffer.toString('base64')`, and `run_record`
  puts every asset into `RESULT` verbatim. That is deliberate — it is how a JSON
  response carries an asset — but it is also why one run is megabytes.
- **Measured per-row sizes** (`octet_length(RESULT)`): 12932 18.2 MB (deck + video),
  12944 11.2 MB, 12948 6.3 MB, 12963/12967 3.8/3.6 MB, 12959 272 B (a failed run, no
  bytes). Nine rows, 136 MB.
- **Measured execution payloads**: `Visual Studio Test` 511 MB / 46 runs,
  `Visual Studio` 377 MB / 92, `File Webhook` 110 MB / 49,
  `LinkedIn Post Sharing` 96 MB / 26, `Visual Studio Prune` 44 MB / 15.
- **n8n's defaults are why this persists.** `DB_TYPE=postgresdb` against
  `datahub-local-core-data-postgresql`, database `n8n` (1444 MB total), no
  `executions.pruneData*` in `settings`, so the built-in 14-day retention applies and
  everything above is *inside* the window.
- **`TemporalFiles` cleanup is request-driven.** `File Webhook`'s `Delete Old File Data`
  removes rows with `updatedAt < $now.minus({ hours: 1 })`, and the node only runs when
  the webhook is called. 19 rows survive from 2026-10-07 17:46–18:46.
- **Nothing references the four dead workflows.** Confirmed by scanning every export's
  `executeWorkflow` `workflowId` and `settings.errorWorkflow` for inbound references,
  and by `grep` for their ids and names.

## Goals / Non-Goals

**Goals:**

- The studio's storage is bounded and proportional to how many runs happened recently,
  not to a week of decks.
- No diagnostics are lost: a failed run keeps its full payload, and a record of every
  run survives.
- The dead workflows are gone from the instance and the repository.

**Non-Goals:**

- Removing the base64-from-JSON contract. It is how a caller receives an asset, and
  changing it means reworking `agent_result`, the studio's response and the LinkedIn
  media branch together. This change bounds the storage instead. (Kept as an open
  question below.)
- Changing n8n's global execution retention. It is an instance-wide env change, and the
  per-workflow setting targets exactly the workflows whose payloads are artifacts.
- Dropping `TemporalFiles` itself. It is live-used by `file_webhook`,
  `image_content_generator` and `visual_studio_test`.

## Decisions

**1. Keep the bytes in the run row; shorten the window from seven days to two.**
The row stays self-sufficient within its window — a caller can still reconstruct a
run's content by `RUN_ID` — and the bound comes from time rather than from stripping
fields. Two days is roughly a dozen runs at the observed rate, so the table settles in
the tens of megabytes instead of 136 MB.
*Rejected:* storing metadata only and refetching from the adapter. It is the smaller
table, but it breaks the documented "a caller can reconstruct every asset ... including
its content" and needs a contract change through three workflows.

**2. Stop persisting successful executions for the workflows whose payload is an
artifact.**
`saveDataSuccessExecution: "none"` on `Visual Studio`, `Visual Studio Test`,
`LinkedIn Post Sharing` and `Visual Studio Prune`; `saveDataErrorExecution` is left at
its default, so a failure still records everything needed to diagnose it. The
execution row itself remains, so `RUN_ID = $execution.id` is unaffected.
*Rejected:* shortening n8n's global retention. It would equally gut the diagnostics of
the scheduled read-only workflows, whose payloads are small and worth keeping.

**3. `Visual Studio Prune` clears `TemporalFiles` with the same one-hour rule the
webhook uses.**
One daily job now owns both tables' expiry, instead of the temp table relying on being
read. The rule is copied rather than invented, so the two cannot disagree about how old
is too old.
*Rejected:* a second schedule or a separate prune workflow for one delete node.

**4. The four dead workflows are deleted, exports included.**
Inactive *and* unreferenced. Deleting the export too matters because the exports are a
backup the instance writes: leaving the file would be re-created on the next backup only
if the workflow still existed, so removing both keeps the repository honest.

## Risks / Trade-offs

- **A two-day window may be too short for a slow approval.** A post authored, then
  reviewed after two days, loses its run row — but not its session: the iteration flow
  keeps `SESSION_ID`, and `visual_studio_error` upserts FAILED rows independently. If
  two days proves tight, the window is one number in one node.
- **`saveDataSuccessExecution: none` removes post-hoc inspection of a successful run.**
  That is the point, but it also means a "why did this render come out odd?" question
  has only the `RESULT` row (STORYBOARD) and the composer's own report. The adapter's
  session directory still holds `index.html`, and the error path is untouched.
- **Deleting a workflow does not delete its executions.** They age out under the
  existing 14-day retention; the four are inactive and their runs are old.
- **The prune job's own execution is now unsaved on success**, so a silently doing-nothing
  prune cannot be inspected after the fact. Its failure path still records, and the row
  counts are visible in the database.

## Migration Plan

1. Land the export changes and the guard test.
2. Delete the four workflows live (`DELETE /api/v1/workflows/{id}`) and remove their
   exports.
3. Apply the four settings and the prune workflow live, publish, re-read and diff.
4. Clear the stale `TemporalFiles` rows.
5. Measure the relations again and record the before/after in the change.

## Open Questions

- Should `agent_result` stop building a data URL and carry the asset as n8n binary, with
  a small `RUN_ID`-addressed fetch for a caller that needs the bytes? That removes the
  base64 from every payload and the run row, and is the real fix if the artifact keeps
  growing (a 30 s deck is already 18 MB).
- Does `Visual Studio Test` need to keep the asset in its response at all, or is the
  download link enough? Its 511 MB is the single largest contributor and it is a manual
  tool.
- Should n8n's own execution retention be shortened for this instance anyway, now that
  the artifact workflows no longer fill it?

## Definition of Done

- The prune workflow uses a two-day window and clears `TemporalFiles`; a guard test
  fails if either is dropped.
- The four artifact workflows carry `saveDataSuccessExecution: "none"`; the guard test
  covers them.
- The four dead workflows are gone from the live instance and from `agents/n8n/workflows/`.
- `TemporalFiles` has no stale rows and the relations are re-measured, with the before
  and after recorded in `tasks.md`.
- `openspec validate --all` passes and the live exports diff clean against the repository.
