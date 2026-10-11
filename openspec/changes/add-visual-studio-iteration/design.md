# Design

## Context

See [proposal.md](proposal.md) — Why. The facts that shape the approach, read from
the adapter, the workflows and the cluster:

- **The adapter resumes a session by id.** `session-server.mjs` spawns
  `pi --print --provider sympozium --model $MODEL_NAME --thinking minimal
  --session-id <id> --session-dir /tmp/pi-sessions <prompt>`. Pi's own help says
  `--session-id <id>` uses the exact project session "creating it if missing". Probed
  live in the session pod: turn 1 asked it to remember `ZEBRA-42`, turn 2 with the
  same id returned `ZEBRA-42`. The transcript is a file under
  `/tmp/pi-sessions/<ISO>_<id>.jsonl` on the session PVC, so it survives a pod restart.
- **The run directory persists too.** `resolveRunDir(workDir, sessionID)` is
  `runs/<id>/` under `SYMPOZIUM_WORKSPACE` (default `/tmp/aivideo`, the PVC). A turn
  `mkdir`s it, stages `gsap.min.js` into it, and writes `index.html` + `out.mp4`
  there. Reusing an id means the next turn starts in the same directory.
- **The id is minted per execution.** `build_author_brief` does
  `sessionId = safe(a.ASSET_TYPE) + '-' + safe(req.RUN_ID)` and `RUN_ID` is
  `String($execution.id)`. So two runs never share a session by construction.
- **The artifact is addressed by the session id.** `ARTIFACT_URL` is
  `/artifacts/<sessionId>/out.<format>` and `resolveArtifact` serves only
  `out.(mp4|gif|webp|png|svg|html)` inside `runs/<id>/`. A stable thread id therefore
  yields a stable URL, and an edit overwrites the thread's output in place.
- **The run row has fixed columns.** `visual_studio_table` is
  `RUN_ID, STATUS, REQUEST, RESULT, ASSET_COUNT, ERROR`; `REQUEST` is already a JSON
  blob. `setup_data_tables.py` is idempotent *by table name* and skips an existing
  table, so adding a column would need a separate migration against live.
- **The prune deletes rows only.** `Visual Studio Prune` is a 04:00 cron plus a
  `dataTable.deleteRows` on `createdAt < now-7d`. It touches no files.
- **The PVC is RWO.** `sympozium_pi_render.storage: 8Gi`, `storageClass: longhorn`;
  `df` in the pod reports 7.8 GiB with 149 MB used, 34 run dirs (92 MB) and 35
  transcripts (11 MB).
- **The queue serializes turns.** `session-server.mjs` chains every turn through one
  promise, so a second turn on the same id cannot interleave with the first.

## Goals / Non-Goals

**Goals:**

- A caller can turn an existing session again and have the composer *edit* the
  composition it already produced, changing what the request names and keeping the
  rest.
- A reviewer's rejection of an animated LinkedIn asset is such an edit.
- Session state (run directory + Pi transcript) is reclaimed after a bounded window,
  so the PVC cannot be filled by abandoned work.
- First authoring is byte-for-byte the behaviour it is today.

**Non-Goals:**

- Version history. An iteration overwrites the thread's `out.<ext>`; keeping every
  revision needs per-turn artifact names and is not asked for here.
- Making iteration cheaper by caching renders or diffing HTML ourselves. One turn is
  still one model run.
- A UI over sessions. The thread id is a parameter and a field in the recorded
  request; a reviewer inspects it there or over HTTP.
- Publishing a video to LinkedIn — still open in `upgrade-visual-studio-authoring`
  task 8.7 and out of scope here.

## Gate findings

- **Pi resumes a `--print` session by id — verified live** (the `ZEBRA-42` probe in
  the running session pod). This is the load-bearing assumption and it holds.
- **The session server can see the previous composition — verified by reading it.**
  It already `mkdir`s the run directory, so a `stat(index.html)` before the turn is
  the only addition; no new request field is needed.
- **A Kubernetes CronJob cannot share the PVC — reasoned, not attempted.** The claim
  is RWO on Longhorn and the session Deployment holds it, so a second pod would fail
  to attach. The adapter owning the sweep is the workable home.
- **The retry does not currently share an id — verified in the export.**
  `execute_visual_studio` maps `CONTENT, ASSET_TYPES, FEEDBACK, FORCE, SCENES` and no
  session id, and `select_article_to_post` carries `row_number`, which is stable
  across the author and the retry.

## Decisions

**1. The caller supplies the thread id; blank means today's behaviour.**
`SESSION_ID` joins the trigger contract as optional. A caller that sets it is
asserting the session exists and wants it continued; a caller that omits it gets a
run-scoped id and a first authoring, exactly as now.
*Rejected:* the studio minting and storing an id on the run row. It would need a
`SESSION_ID` column, a live table migration, and a "pick a prior thread" surface —
all for a value the caller already knows.

**2. A continuation is expressed by the id, not by a flag.**
`SESSION_ID` present *is* "continue". There is no `MODE` parameter to keep in sync
with it, and no way to pass a session id yet mean "start fresh".
*Rejected:* a separate `ITERATE=true`. Two fields that must agree are a drift surface.

**3. The session server decides author vs edit from the directory, not the caller.**
Before a turn it checks whether `runs/<id>/index.html` exists. If it does, the tail
instruction becomes "apply the request to the composition already here, then
re-render" instead of "write the composition and render". The caller's intent shapes
the *brief*; the filesystem decides the *instruction*.
*Rejected:* trusting the caller's declaration alone. `SESSION_ID` set on a session
that was swept or never existed must degrade to a first authoring rather than tell
the composer to edit a file that is not there.

**4. The change is the existing free text; no new field.**
`build_author_brief` already appends `FEEDBACK` ("Correction from a reviewer") and
`EXTRA_PROMPT` ("Extra direction from the caller") verbatim, after the motion rules.
An iteration sends one of those with the thread id. `EXTRA_PROMPT` is the natural
field for a deliberate change; `FEEDBACK` covers the reviewer path.
*Rejected:* a `CHANGE` field. It would be a third synonym for "free text appended to
the brief", with no behaviour to distinguish it.

**5. Rejection continues the thread.**
`LinkedIn Post Sharing` derives `SESSION_ID` from the article
(`lips-<row_number>`), so the author and the retry share it and the retry edits the
rejected video.
*Trade-off:* this supersedes the "a rejection has to be free to re-author" stance in
`AGENTS.md`. It is a deliberate reversal: re-authoring was chosen when the composer
could not see its previous work, and the cost of losing an approved composition now
outweighs the freedom. A caller that genuinely wants a fresh take sends no
`SESSION_ID` (the manual triggers still default to one).

**6. Retention is a TTL sweep inside the adapter, 7 days by default.**
`session-server.mjs` removes `runs/<id>/` and `pi-sessions/*_<id>.jsonl` older than
`PI_RENDER_SESSION_TTL_DAYS` on startup and, throttled, after each turn, skipping the
session in flight. The window is an adapter default read from that variable.
*Rejected:* a CronJob (RWO PVC), and driving it from `Visual Studio Prune` (couples a
workflow to the adapter's filesystem and only runs if n8n is healthy). The adapter
owns both stores, so it owns their expiry.
*Corrected while implementing:* the window is **not** a chart value. `AgentRuntime`
(the session's spec) has no `env` field and the controller passes a fixed environment
(`SYMPOZIUM_*`, `MODEL_*`, the provider keys — read off the live Deployment), so
`templates/pi-render-session.yaml` has nothing to render into. The variable is
honoured when set, so the window moves without an image rebuild the day a passthrough
exists; today the default in the image is the only mechanism.
*Also rejected:* an explicit `DELETE /sessions/<id>` for now. Nothing needs to drop a
thread early yet, and the TTL covers abandonment; it can be added without changing
the model if a "thread finished" signal appears.

**7. The thread id is recorded inside `REQUEST`, not as a new column.**
`run_record` adds `SESSION_ID` to the `REQUEST` JSON it already builds.
*Rejected:* a table column, which needs a live `visual_studio_table` migration for a
field only used to join a thread's turns.

## Risks / Trade-offs

- **A swept thread that is later continued authors fresh.** If a post is authored,
  approved after the TTL, and then rejected, the id resolves to an empty directory
  and the turn is a first authoring. This is graceful (the same result as today) but
  the reviewer's "change this" becomes a full rebuild. The window is the mitigation;
  raise `retentionDays` if approvals run slow.
- **An overwritten artifact breaks a bookmarked URL's meaning.** The thread URL
  serves the latest revision. Acceptable because the URL is the thread, and version
  history is a non-goal.
- **The sweep must not race a turn.** It skips the session in flight and runs before
  or after the serialized turn, never inside one; a session's mtime also updates on
  its own turn, so an actively iterated thread is out of range.
- **An edit can still start over.** If the composer decides the composition is
  unsalvageable it may rewrite `index.html`; the instruction asks for an edit, it does
  not enforce one. The Pi transcript makes the previous work *available*, not
  mandatory.

## Migration Plan

1. Land the adapter change (instruction helper, stat branch, sweep) and its unit
   tests; no workflow depends on it yet.
2. Land the `SESSION_ID` contract on the three triggers, `normalize_input`,
   `build_author_brief` and `record_run`; blank is the default, so live behaviour is
   unchanged until a caller sends one.
3. Land the LinkedIn per-article thread id, so a retry edits.
4. Apply live with `--require-edge` guards, publish, re-read, and diff the export
   against live — the same sequence as `upgrade-visual-studio-authoring`.
5. Confirm the sweep logs on the running session after the image rolls.
6. Verify by hand: author with a thread id, then send a second turn with a change and
   confirm the artifact changed and the directory was reused.

## Open Questions

- Should an iteration return the previous revision alongside the new one, so a
  reviewer can diff them? Today only `out.<ext>` exists, and `RESULT` carries the new
  asset. Deferred to version history.
- Should a thread be dropped when its post reaches `PUBLISHED` or `CANCELLED`? The
  TTL covers it; an explicit drop is cheap to add later (decision 6).
- Should the retention window be per asset kind (a deck leaves 8-18 MB, a GIF 4-5 MB)?
  Not worth the knob until the PVC is actually under pressure.
- Does the sweep need to be visible in the run table, so a "thread expired" is
  explainable? Today it is a log line on the session pod.

## Definition of Done

- `SESSION_ID` is on all three triggers, in `normalize_input`, in `build_author_brief`
  and inside the recorded `REQUEST`; a blank value reproduces today's run-scoped id.
- A second turn with the same `SESSION_ID` and a change edits `index.html` in place
  and re-renders, verified live against the deployed session.
- The session server picks author vs edit from the run directory, and the adapter unit
  tests cover the instruction and the sweep selection.
- `LinkedIn Post Sharing`'s animated branch passes a per-article `SESSION_ID` stable
  across the retry, asserted offline.
- Expired runs and transcripts are reclaimed on the configured window, with the
  in-flight turn never swept.
- `AGENTS.md`, the adapter `README.md` and the change's tasks are updated; the
  reversal of the "free to re-author" stance is written down where it is read.
