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
- [x] 5.3 Built by CI and pinned in `bedd064` (`sha256:0c295807…`), rolled by ArgoCD; the
  pod is `Ready` and `sympozium-pi-render-session` in the image contains `turnInstruction`.
  The startup sweep ran (no removals on a fresh pod, as expected).
- [x] 5.4 Live, end to end through the studio. Turn 1 (execution 12963) authored
  `runs/e2e-thread-1/index.html` (18,049 B) and `out.mp4` (2,842,992 B) under the named
  session id. Turn 2 (execution 12967) with the same `SESSION_ID` and an
  `EXTRA_PROMPT` change ran on the same directory: `index.html` 18,049 → 18,428 B (md5
  680e313e… → 06edeff4…), `out.mp4` re-rendered (md5 dec38024… → 1caf0966…, 300 frames,
  10 s), one transcript for both turns (51 → 73 lines, 220,176 → 300,068 B), and the turn-1
  fonts/assets left in place. The brief carried the continuation line and the change and no
  "Plan first:"; the composer reported *"Applied both changes in place and re-rendered"* and
  listed only the two requested edits. (A first attempt, execution 12959, landed while the
  image was rolling and failed with `ECONNREFUSED`; it was cleaned and re-run.)
- [x] 5.5 Live: planted `runs/sweep-old/` and `2020-01-01T00-00-00-000Z_sweep-old.jsonl` with
  a 2020 mtime beside a recent pair; a pod restart logged
  `swept expired session sweep-old` and `swept expired transcript 2020-01-01T00-00-00-000Z_sweep-old.jsonl`
  and left the recent directory and transcript untouched.
- [x] 5.6 Applied live with `--require-edge` guards, all satisfied. The PUTs published in
  place (`active: true` unchanged, `activeVersion` equal to the top level); the export diffed
  against live shows no parameter or connection differences for either workflow.

## 6. Documentation

- [x] 6.1 `AGENTS.md` § Visual Studio: `SESSION_ID` in the trigger contract, a new *A session
  is a thread* paragraph (durability, author-vs-edit, the retention window), and the
  LinkedIn bullet rewritten from "No frozen spec" to "A rejection continues the thread",
  naming the reversal.
- [x] 6.2 `agents/adapters/pi-render/README.md`: a *A session continues, and expires* section
  — one directory and one transcript per thread, the directory deciding author vs edit, and
  the retention window with why the TTL is an image default.
