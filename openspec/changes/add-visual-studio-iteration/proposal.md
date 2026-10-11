# Proposal

## Why

Every studio run mints a throwaway session. `build_author_brief` sets
`session_id = <ASSET_TYPE>-<executionId>`, so each execution gets a new Pi transcript
and a new `runs/<id>/` directory, and nothing carries the work forward:

- **A rejection re-authors from scratch.** A reviewer who wants one thing changed
  ("end on a visible idle", "make the headline bigger", "slow scene 3") sends
  `FEEDBACK`, the workflow normalizes it, and the composer starts over on a full
  brief with a fresh directory. The work already approved is thrown away and the
  same mistakes are reachable again.
- **The adapter is already session-capable; only the workflow is not.**
  `session-server.mjs` runs `pi --session-id <id> --session-dir /tmp/pi-sessions`,
  and Pi *resumes* an existing session by id (verified: a token planted in turn 1 was
  returned in turn 2). The run directory `runs/<id>/` keeps `index.html`, `assets/`
  and `out.mp4` on the same PVC. Reusing the id is all that is missing.
- **Nothing ever deletes session state.** `Visual Studio Prune` deletes *table rows*
  older than 7 days; `runs/<id>/` and `pi-sessions/*_<id>.jsonl` are never removed.
  The PVC is 7.8 GiB with 149 MB used (34 runs / 92 MB, 35 transcripts / 11 MB) — a
  slow leak today, but a render loop fills it and then **every turn fails**. Threads
  make it structurally worse, because a directory is meant to persist between turns.

## What Changes

- **A thread id is an optional trigger parameter.** `SESSION_ID` joins the trigger
  contract. Blank keeps today's behaviour (a run-scoped id and a fresh author); a
  caller that supplies one is asserting the session exists and wants it continued.
- **A continuation is an edit, not a re-author.** When `SESSION_ID` is present,
  `build_author_brief` says so, and the request's change (`EXTRA_PROMPT`, or a
  reviewer's `FEEDBACK`) is applied to the composition already in the run directory.
  The artifact URL is stable for the thread, so the caller's fetch is unchanged.
- **The session server decides author vs edit from the directory.** It checks for
  `index.html` in the run directory before the turn and switches its trailing
  instruction accordingly: *write the composition* or *edit it in place and
  re-render*. That makes the behaviour correct even when the caller's declaration and
  the filesystem disagree, and it needs no new contract field.
- **A rejected LinkedIn animation continues its thread.** The animated branch derives
  its `SESSION_ID` from the article it is publishing, so it is stable across the
  retry, and the retry edits the rejected video instead of rebuilding it.
- **Session state has a retention window.** The session server sweeps `runs/` and
  `pi-sessions/` whose mtime is older than a TTL (chart-configurable, default 7 days)
  on startup and throttled after each turn, skipping the turn in flight. A thread
  still being iterated has a fresh mtime, so an active thread is never swept.
- **The thread id is recorded.** The run row carries it inside the existing `REQUEST`
  JSON, so a thread's turns are joinable without a table migration.

## Capabilities

### New Capabilities

- `visual-iteration`: a studio run can continue a prior run's session, editing the
  existing composition and Pi transcript rather than authoring a new one; session
  state has a retention window and is reclaimed when it expires.

### Modified Capabilities

- `visual-studio`: the trigger contract gains an optional `SESSION_ID`; a run's
  recorded request carries it; a continuation is distinct from a first authoring.
- `agent-authored-compositions`: the authoring runtime keeps per-session state across
  turns, serves an edit turn against the previous composition, and reclaims expired
  session state.
- `linkedin-post-publishing`: a rejected animated asset continues the session that
  produced it, so the retry fixes the rejection instead of re-authoring.

## Impact

- `agents/adapters/pi-render/session-lib.mjs` — a pure `turnInstruction({format,
  isIteration})` helper plus the retention TTL/selection helpers, unit-testable.
- `agents/adapters/pi-render/session-server.mjs` — stat the run directory to pick
  author vs edit; sweep expired runs and transcripts.
- `agents/adapters/pi-render/test/session-lib.test.mjs` — cover the instruction and
  the sweep selection.
- `agents/adapters/pi-render/README.md` — the session lifecycle and retention.
- `agents/n8n/workflows/visual_studio.workflow.json` — `SESSION_ID` on the triggers
  and `normalize_input`, the continuation brief, the thread id in the run record.
- `agents/n8n/workflows/linked_in_post_sharing.workflow.json` — the animated branch
  passes a per-article `SESSION_ID` so a retry edits in place.
- `agents/n8n/scripts/test_visual_studio_graph.py`, `test_linkedin_animated_media.py`
  — assert the contract and the stable thread id.
- `AGENTS.md` — the Visual Studio section: sessions, iteration and retention.
