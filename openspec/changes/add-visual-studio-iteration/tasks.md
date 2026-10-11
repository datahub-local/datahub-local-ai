# Tasks

## 1. Adapter: author vs edit (`agents/adapters/pi-render/`)

- [x] 1.1 Added `turnInstruction({ format, isIteration })` to `session-lib.mjs`, returning
  the trailing instruction for the six cases (mp4/gif/webp/png, svg, html) × (author,
  edit), plus `compositionMarker(format)` — `index.html`, or `out.svg`/`out.html` for
  those types — which is what decides the case.
- [x] 1.2 `session-server.mjs` `stat`s the session's composition marker before the turn and
  passes `isIteration` to `turnInstruction`, replacing the inline per-format tail. A
  missing file, a swept session or a first turn all resolve to the author instruction.
- [x] 1.3 Unit-tested in `test/session-lib.test.mjs` (every format has an author and an edit
  variant, the edit names the existing artifact and the author does not) and end to end in
  `test/session-server.test.mjs` (the stub Pi records its prompt; the second turn in one
  session is an instruction to edit, the first is not). Verified the end-to-end assertion
  fails when the server hardcodes `isIteration = false`.

## 2. Adapter: session retention

- [x] 2.1 `sessionIdFromTranscript`, `expiredRunDirs` and `expiredTranscripts` added to
  `session-lib.mjs`, so the policy is pure and testable.
- [x] 2.2 `sweepSessions` in `session-server.mjs`: on startup and throttled (hourly) after a
  turn, it removes expired run directories and transcripts, never the session in flight,
  best-effort with a log line per removal and a logged failure that does not fail the turn.
  The TTL is `PI_RENDER_SESSION_TTL_DAYS`, default 7; `0` disables the sweep.
- [x] 2.3 Unit-tested: older-than-cutoff is returned, the boundary and newer entries and the
  in-flight id are not, and an unparsable or foreign transcript name is left alone.
- [x] 2.4 No chart change: `AgentRuntime` has no `env` field and the controller passes a
  fixed environment (verified against the live session Deployment and the CRD), so the
  window cannot be rendered from values. The default (7) lives in the adapter and
  `PI_RENDER_SESSION_TTL_DAYS` is read when set, so it moves without a rebuild once a
  passthrough exists.

## 3. Visual Studio workflow (`agents/n8n/workflows/visual_studio.workflow.json`)

- [x] 3.1 `normalize_input` accepts and returns `SESSION_ID`; `main_trigger` and
  `form_trigger` carry it (the webhook passes the body through). Both export copies edited.
- [x] 3.2 `build_author_brief` uses the request's `SESSION_ID` verbatim and falls back to
  `<type>-<RUN_ID>` when blank; a named session swaps the branch's "plan first" line for a
  continuation line ("apply the change below to it and keep everything else"). The adapter
  `session_id` is the resolved value, and the artifact URL is addressed by it.
- [x] 3.3 `run_record` includes `SESSION_ID` in the `REQUEST` JSON it already builds.
- [x] 3.4 Added three tests to `test_visual_studio_graph.py`: the contract carries
  `SESSION_ID` and the id reaches the adapter `session_id` with the run-scoped fallback
  intact; a continuation brief differs from a first authoring and every authoring branch
  chooses between them; the recorded request carries the session. All six (two copies ×
  three) verified to fail without the export change.

## 4. LinkedIn retry (`agents/n8n/workflows/linked_in_post_sharing.workflow.json`)

- [x] 4.1 `execute_visual_studio` passes `SESSION_ID` as
  `=lips-{{ $('select_article_to_post').item.json.row_number }}` in both copies and in the
  mapping schema, so the author and the retry share one and the id does not depend on the run.
- [x] 4.2 Added `test_the_animation_keeps_one_session_across_a_retry` to
  `test_linkedin_animated_media.py`: the call names a session, the id does not reference
  `$execution`, and it is derived from the row. Both copies verified to fail without the change.

## 5. Verify

- [x] 5.1 Offline suites green: `agents/n8n/scripts/` **188 passed** and the adapter
  `node --test` suite **33 passed**.
- [x] 5.2 No chart change in this change (see 2.4), so there is nothing new for the render
  gate; `helmfile template` was not re-run here and CI renders the chart on every push under
  `agents/sympozium/**`.
- [ ] 5.3 Rebuild and pin the adapter image; confirm the session pod rolls and the sweep
  logs on startup. Blocked: no Docker daemon locally, so the image builds from CI on push.
  **[UNVERIFIED until built]**
- [ ] 5.4 Live: POST one authoring request with a fresh `SESSION_ID`, then a second turn
  with the same id and a change; confirm the same run directory is reused, `index.html`
  changed, the artifact re-rendered and the transcript spanning both turns.
- [ ] 5.5 Live: confirm a thread older than the window is swept, and that a turn on a swept
  id authors fresh rather than failing. Needs the same image as 5.3 (the sweep is in it);
  a directory planted with an old mtime makes the sweep observable without waiting a week.
- [ ] 5.6 Apply the two workflow changes live with `--require-edge` guards, publish, re-read
  `activeVersion` and diff the export against live. Held until the adapter image carrying
  the edit instruction is rolled, so the LinkedIn thread id does not reuse a directory on an
  image that would re-author into it.

## 6. Documentation

- [x] 6.1 `AGENTS.md` § Visual Studio: `SESSION_ID` in the trigger contract, a new *A session
  is a thread* paragraph (durability, author-vs-edit, the retention window), and the
  LinkedIn bullet rewritten from "No frozen spec" to "A rejection continues the thread",
  naming the reversal.
- [x] 6.2 `agents/adapters/pi-render/README.md`: a *A session continues, and expires* section
  — one directory and one transcript per thread, the directory deciding author vs edit, and
  the retention window with why the TTL is an image default.
