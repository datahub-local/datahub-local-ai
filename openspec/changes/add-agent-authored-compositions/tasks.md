# Tasks

## 1. The proven sample

- [x] 1.1 Author a composition from a one-sentence brief, following the HyperFrames skill contract, and render it offline; verify with the engine's own `lint` and by rendering in the image toolchain (verified 2026-10-04: `agents/render-samples/agent-flow/index.html`, brief "a smooth, modern animation showing how a team of AI agents collaborates to build a project". `lint` caught two real defects — a GSAP tween on `top` (must be a transform) and a timed element with no `id` — both fixed to reach **0 errors**. Rendered 1080×1350, 270 frames, 9.000 s, H.264 in the render service's image, timeline ready in 648 ms with no readiness warning)
- [x] 1.2 Commit the composition, the render and a preview with the procedure that produced them, and record the engine version; verify a reader can reproduce the render from the committed source without re-authoring (verified: `agents/render-samples/agent-flow/` holds `index.html`, `agent-flow.mp4`, `agent-flow.gif`; `agents/render-samples/README.md` states the brief, the loop, the two lint findings and the offline re-render commands. Engine `0.8.123`)

## 2. The Pi gate

- [x] 2.1 Hand-apply an `AgentRun` with the Pi harness (`runtimeRef: pi-session-v0-84-4`, digest recorded) on a throwaway persona, given a brief that requires authoring a composition, and stream its log while the pod lives; verify the run's outcome is recorded rather than inferred (**answered, and the premise was wrong: Pi cannot host an `AgentRun` at all.** The admission webhook rejects it — `harness: runtime "pi-session-v0-84-4" is session-only (v1alpha2); start it as a HarnessSession instead of an AgentRun`. Every persona here runs as an `AgentRun`, so Pi is not a drop-in runtime. Evidence and the full path to a live session in `pi-harness-findings.md`)
- [x] 2.2 Check the three capabilities the work needs — write a composition file, run the engine's validation and render commands, and reach the toolchain (Node, Chrome, FFmpeg, vendored GSAP) — and record each as pass or fail with the evidence; verify the finding is written down even when a check fails (**answered 2026-10-04: file write PASS, shell PASS, toolchain FAIL.** After the `OPENAI_API_KEY` fix the session reached `Ready` (`1/1`, zero restarts, listening on 8080) and the checks ran: `echo ok > probe.txt` round-tripped, `sh` is present, **node v22.19.0 present but chromium/ffmpeg/ffprobe absent**, no python3, no hyperframes package. The decisive finding is not the missing binaries but the harness contract: both adapter paths spawn Pi with `--no-tools --no-skills`, so it has **no file write, no shell and no edit** even though the pod has a shell, and cannot read the authoring skills. Pi is a text-in/text-out completion endpoint)
- [x] 2.3 Decide from the evidence: if the probe passes, add the persona per 3.1; if it fails, record why and whether the harness image needs the toolchain or the path stays out-of-fleet; verify the decision and its reason are recorded either way (**decided: the path stays OUT-OF-FLEET.** Pi cannot author a composition — `--no-tools` excludes the very operations the work needs, so a harness image with Chrome and FFmpeg baked in would still be unable to invoke them. Authoring runs where tool use and the toolchain already exist: the render image, as proven by `agents/render-samples/agent-flow/`. 3.1-3.3 are dropped rather than blocked, since no credential, image or config change reaches this. Pi remains fit for text work. The credential fix stayed — it unblocked the gate and is correct for any v1alpha2 harness — and the full evidence is in `pi-harness-findings.md`)

## 3. The in-fleet path (SUPERSEDED — our own adapter runs Pi with tools)

The "dropped" conclusion below was right about the **maintained** Pi/Hermes adapters
and wrong as a general claim: tool use is the adapter image's business, so a
purpose-built adapter can enable it. `agents/adapters/pi-render/` is that adapter —
our render image plus `pi`, with `--no-tools` and `--no-skills` dropped — and a run
against it reached `Running` with Pi executing in-cluster.

- [x] 3.1 ~~Add a persona with `runtimeRef` pinned to the probed runtime~~ — built as `agents/adapters/pi-render/` plus a spike `AgentRuntime`, since the maintained runtimes are session-only
- [ ] 3.2 Run it by hand-applied `AgentRun` and verify it authors, lints, corrects and renders; record the outcome (**the authoring loop is PROVEN; the render is blocked by a resource limit that cannot be raised.** Four runs on 2026-10-04:

  **What works, observed live.** Pi wrote `/workspace/index.html`, and **revised it four times** (10,390 → 11,537 bytes) while running `hyperframes lint` and `hyperframes check` with real headless Chromium, reading the structured findings and correcting against them — including `check --samples 15 --at-transitions`, `check --json` parsing the JSON, and filtering output by section (`/Layout/,/Contrast/`, `/Motion/`). It produced `snapshots/` with real rendered frame PNGs and an `index.motion.json`. This is the thesis confirmed: a coding agent's read/edit/run loop fits composition authoring, and it uses the engine's own gate without being told to beyond the method file.

  **What blocks it.** Every run was **OOMKilled** before an `out.mp4` existed — `agent` container, exit 137. The container's limit is **1Gi** and cannot be raised: a sweep of **every Sympozium CRD** found the field nowhere. `Agent.spec.resources` and `AgentRun.spec.resources` are both **rejected** (`unknown field`), `AgentRun.spec.sandbox.resources` creates a *separate* container, and `AgentRuntime.spec.resources` exists and is documented as *"the primary container's requests/limits"* but **the controller never applies it** — patched to 6Gi with `Ready=True`, the pod still reads 1Gi. The agent container's resources are **hardcoded** in `agentrun_controller.go`. Docs, and three external sources, all name fields that do not exist in this version. **That is the precise upstream report.**

  **What does work: `AgentRun.spec.env`.** The controller appends it to the agent container last, so `NODE_OPTIONS=--max-old-space-size=512` reaches the render — verified in-cluster with a **524 MB heap cap** inside the container. With that plus `--low-memory-mode --workers 1` in the prompt, **run 8 got further than any other**: it wrote `index.html` and `index.motion.json` and **actually started a render** (a `work-…` directory appeared), surviving 4 minutes inside a 1Gi container. Correction to an earlier note here: runs 1–6 never invoked `hyperframes render`; run 8 did. It still OOMed — the render alone exceeds 1Gi even with one worker and a capped heap.

  **Established:** the limit is hardcoded at 1Gi, no field raises it, and eight attempts produced no `out.mp4`. A render *does* complete under a 1Gi cap outside the harness contract (measured, 12–18 s), which is how `agents/render-samples/` was produced.

  Renders also warn in advance: *"5 capture workers may exceed this process's V8 heap (limit 4144MB supports ~4)"*. **Not verified:** whether it would reach a render with adequate memory; it has never had any.

  **Run 5, on the corrected prompt, died EARLIER and invalidated part of this.** With `--low-memory-mode` required in the prompt, the run was OOMKilled after **70 seconds** having written nothing — no `index.html`, and no `hyperframes` process ever launched. Runs 1 and 2 lived 8 and 2.5 minutes and wrote the composition four times. So the render is **not** the only thing that exhausts the memory, and the low-memory flag removes one cause, not all: an OOM can land during model startup before any composition exists.

  **Brief length is a real variable — controlled test, run 6.** Same image and prompt as run 5, with run 1's longer brief restored: it survived past 70 s, wrote `index.html` at **t+150 s**, and was OOMKilled at **~4 minutes**. So a longer brief keeps the model busy long enough to get a composition on disk, where a one-sentence brief died before writing anything — but it still OOMs. Low-memory mode was never reached in either run: `hyperframes render` was never invoked, and no `screenshot capture` line appears in any log.

  **Established:** the limit is 1Gi; it cannot be raised from any object this repository controls; and a run OOMs somewhere between model startup and a render, with brief length shifting *when* rather than *whether*. **Not established:** that this adapter can complete a run on v0.10.87 at all — six attempts, no `out.mp4`. The one proven render of the sample came from **outside** the harness contract, under our own `--memory 1g` cap, which is where `agents/render-samples/` was produced.)
- [x] 3.3 Confirm the runtime's digest is recorded — `status.resolvedImageDigest` is `sha256:0dfd4e99…`, the amd64 digest of the published multi-arch image

**Admission finding, which cost several attempts and is worth recording.** A harness
run whose `spec.toolPolicy` is **absent** is rejected with
`task.mode "harness" does not support [toolFilter] … (mode supports: [persona])`,
even though the Agent and its `SympoziumPolicy` both leave `toolGating` unset and the
CRD defaults nothing. Something before the webhook materialises a non-nil
`toolPolicy`, and `RequestedCapabilities` (`internal/controller/taskmodes/capabilities.go`)
then reads `len(tp.Allow) > 0 || len(tp.Deny) > 0` as a request for `toolFilter`.
Passing an **explicit empty** `toolPolicy: {allow: [], deny: []}` makes it pass. So
the adapter declares `persona` only — it maps `SYSTEM_PROMPT` onto Pi's system prompt,
and does **not** translate `TOOL_POLICY_*` onto Pi's own tool selection, which is
exactly the honest claim.


## 4. Scope reconciliation

- [ ] 4.1 Re-scope `migrate-render-layouts-to-catalog-blocks` in its proposal, design and tasks to "add catalog data blocks alongside the hand-written layouts": the catalog can back only `comparison` and `stats`, so its original goal of removing every layout is unreachable; verify the change validates and its unsatisfiable tasks are either removed or marked blocked with the reason
- [x] 4.2 Confirm the render service's contract is untouched by this change — it still rejects caller markup and its spec vocabulary is unchanged; verify by running the existing offline suite and the markup-rejection test (verified 2026-10-04: 27 offline tests pass, including *markup is not accepted as a spec* and *the service refuses caller markup before composing*. The new path adds no field to the service and no key to `MARKUP_KEYS`)
- [x] 4.3 State in the sample README and the render service's README which product answers which need, so a caller does not reach for the wrong one; verify both cross-reference each other (verified: `agents/render-samples/README.md` has a *Relationship to the render service* section; `agents/n8n/render/README.md` has a *What this service is not* section naming the bespoke case and pointing at the samples)

## 5. Hygiene

- [x] 5.1 Add the render-samples directory to CI only if a check exists that does not need Chrome (e.g. a lint that can run headless); otherwise record explicitly that samples are verified by hand and why; verify the decision is written down rather than left implicit (**decision: no CI job.** `hyperframes lint` is an error gate on the composition, and `render` needs Chrome + FFmpeg, so a real check means building the image in CI — which the `render-image` job already does for the render service. Authoring is a human/agent step producing a committed artifact, not a repeatable build output, so a per-sample CI job would rebuild a 500 MB image to re-render a file nobody changed. The samples are verified by hand with the commands in `agents/render-samples/README.md`; re-verify when the engine version moves)
- [x] 5.2 Record the engine version pinning and the offline rule where a new composition author will find them (the sample README), and re-verify a fresh clone can re-render from the committed source (verified 2026-10-04: reproduced from only the committed `index.html` + a copied `vendor/gsap.min.js`, rendering under `docker run --network none` — the engine reports `0 errors` from lint and produces 1080×1350 / 270 frames / 9.000 s, matching the committed MP4. Engine `0.8.123`; the offline rule is stated in the sample README)
