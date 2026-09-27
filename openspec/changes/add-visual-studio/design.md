# Design

## Context

See `proposal.md` for motivation and `specs/visual-studio/spec.md` for the behavior contract. Only the constraints that shape the n8n approach are recorded here, and they were verified in-cluster, not assumed.

- **The studio is generic and stateless between runs.** Every parameter arrives on the trigger: `CONTENT` (required), `ASSET_TYPES`, `FEEDBACK`, and an optional frozen `SPEC_JSON`. Three triggers share the one contract — an `executeWorkflowTrigger` (sub-workflow call, the shape `Article Content Writer` uses), a `webhook` (`POST /webhook/visual-studio`), and a `formTrigger`. It reads no caller state from a table or sheet. This is the same shape as `LinkedIn Image Creator`, which takes `POST_CONTENT` in and returns `omImage` out.
- `LinkedIn Image Creator` is the flow the raster path reuses: LLM art director → LiteLLM `POST .../openrouter/images` (model `google/gemini-3.1-flash-image`, `aspect_ratio`, `resolution`) → decode `data[0].b64_json`. Prompts and datasets are files fetched by `DownloadTemplate` from `agents/n8n` in the backup repo, and that path reads **GitHub `main`** — new files must be committed and pushed before the workflow can resolve them (learned the hard way: the first live run failed with "resource not found" until `visual_types.json` was on `origin/main`).
- **`n8n-nodes-puppeteer` v1.5.0** exposes `Get Page Content`, `Get Screenshot` (png/jpeg/webp), `Get PDF`, and **`Run Custom Script`**. It connects to browserless at `ws://datahub-local-core-automation-n8n-chromium:3000?token=...`. The node navigates to its `url` (a `data:` URL for us) before running the script; the script must `return [...]` an array of items.
- **browserless/chromium v2.56.7** serves `screenshot`/`pdf`/`content`/`scrape` over HTTP and a Puppeteer/CDP WebSocket; it bundles Playwright's `ffmpeg-linux` inside its own image, but that binary is not reachable from n8n.
- **GraphicsMagick 1.3.47** runs in the n8n image with GIF and WebP delegates. Verified in-cluster on 2026-09-27: `gm convert -list format` reports `GIF P rw+` (multi-image) but `WEBP P rw-` (single-image) — `gm` can assemble animated **GIF only**. No `img2webp`, `webpmux`, `cwebp`, `gif2webp` or `ffmpeg` exists in the image.
- **`ExecuteCommand` is disabled by default in n8n v2 and is enabled on this instance** (`NODES_EXCLUDE=[]`), and `img2webp` comes from the `webp-converter` extra module (`custom.extra_modules`), installed globally at boot into `/usr/local/lib/node_modules/webp-converter/bin/libwebp_linux/bin`. Verified 2026-09-27: `img2webp -loop 0 -d 83 f_*.jpg -o out.webp` turned 36 captured JPEG frames into a 36-frame animated WebP (3.73 MB, 1200x1500, loop 0, JPEG input accepted).
- The n8n image also contains `EditImage`, `Files` (read/write from disk, rooted at `~/.n8n-files`) and `Code` nodes. `EditImage` cannot assemble an animation. n8n is **2.41.3 on Postgres** with the `DataTable` node available. The Files node cannot write `/tmp` (`N8N_BLOCK_FILE_ACCESS_TO_N8N_FILES` defaults to true and is not overridden), so the renderer writes frames under `~/.n8n-files`, never `/tmp`.
- **The DataTable public API is real** (verified live: `GET/POST /api/v1/data-tables`, row get/insert/update/upsert/clear/delete, column create/update/delete), and the `n8n-nodes-base.dataTable` node has a row `upsert` with filter conditions. `visual_studio_table` is provisioned by `scripts/setup_data_tables.py` (idempotent by name), the same "documented setup step" pattern as `article_drafts` in `add-content-writer-agent`.
- The blog and its conventions live in `add-content-writer-agent/design.md`. That change is one **caller**: it will pass the article text as `CONTENT`, request `hero_static` first in `ASSET_TYPES`, re-present a rejected variant by passing the frozen spec back as `SPEC_JSON`, and own every Slack gate, the per-asset review state and the commit. This change ships none of that.

## Goals / Non-Goals

**Goals:**
- One workflow, many output types, driven by a registry file rather than by branches in the workflow.
- One parameter contract, three trigger surfaces: sub-workflow call, HTTP API, form.
- Stateless between runs: nothing is read back to decide what to produce; a run record is written so the outcome can be fetched later.
- Animation with no new service and no video model: browser timeline → frames → `img2webp`.
- Model output is data; markup is deterministic.

**Non-Goals:**
- True video (`motion_clip`). Declared, reported unavailable; it needs `ffmpeg`, which is not in the n8n image.
- Per-asset review state, Slack gates, retries-with-feedback and the commit. Those belong to the caller (`add-content-writer-agent`); the studio performs neither a review nor a commit.
- Article concepts of any kind inside the workflow: no `ENTRY_ID`, no queue, no markers, no slug.
- A Sympozium agent, an MCP server, or any cluster change beyond the already-decided n8n env.
- Free-form model-authored HTML/SVG (rejected in D2).

## Decisions

### D1. A registry file is the type axis

`datasets/visual_types.json` declares each type: `{id, author, template, render, format, aspect, budget}` plus the request-level `budget`, `motion_kinds`, `max_types_per_request` and `default_types`. The workflow reads it, filters to the requested types, and routes each through its declared render mode. Adding a type is a data change.

*Alternatives considered:* a separate sub-workflow per type — rejected; it multiplies workflows and hides the common authoring stage. Hard-coded `switch` branches — rejected; the registry is the repo's existing dataset pattern (`image_motifs.json`). Registry-driven static-raster art direction — rejected; the tuned `image_motifs.json`/`HOOK_TREATMENT` axis stays for the raster path, and the registry governs structure, render mode and format only.

### D2. Two-stage authoring: model emits a content spec, code emits markup

Stage 1 asks the model for a typed JSON spec: `{title, blocks:[{label, value}], accent, motion:{kind, durationMs}, alt}`. Stage 2 is a Code node that fills a template file (`templates/infographic.html` or `templates/infographic.svg`) from the spec and fails on any unresolved `%%TOKEN%%`, so no partially filled page can reach a renderer. Static raster types keep the art-director → image-model path, with the prompt derived from `CONTENT` plus the spec so the raster matches the markup.

*Alternatives considered:* model writes HTML/SVG directly — rejected; this is the Mermaid/Kroki lesson the repo already paid for, and it makes static and animated variants diverge. A schema-less free string — rejected; a missing field must fail loudly.

### D3. Animation is frame-stepped from the browser, then assembled

The markup is rendered from a `data:text/html;base64,...` URL at a fixed viewport. A Puppeteer **custom script** waits for `document.fonts.ready`, pauses every animation, and for `i` in `0..N-1` sets each animation's `currentTime` to `i * 1000/fps`, awaiting a frame and screenshotting to **JPEG** (smaller than PNG; `img2webp` re-encodes anyway). Frames are written under `~/.n8n-files/<execution>/<asset>/` — the only root the Files node may write — and written through promptly so the execution does not carry all of them at once. `ExecuteCommand` runs `img2webp -loop 0 -d <ms> <frames> -o <out>` (GIF fallback: `gm convert -delay <100/fps> -loop 0 <frames> <out>`) against the same directory; the result is read back as binary.

Frame count, fps and duration come from the type and spec, never from wall-clock recording, so a run is reproducible and a re-render is comparable.

*Alternatives considered:* CDP screencast / wall-clock recording — rejected as non-deterministic and heavier on browserless. Playwright video via the chromium pod's ffmpeg — rejected; not reachable from n8n. A video model — rejected; none is configured and infographic text mangles. `/tmp` — rejected; the Files node cannot write it without disabling a security default instance-wide.

### D4. Animated WebP is the committed format, GIF the fallback

The committed animated asset is **WebP**, encoded with libwebp's `img2webp` from the captured frames; `gm` in this image cannot write an animated WebP (`WEBP P rw-` is single-image, verified 2026-09-27), so `gm` is the **GIF fallback** when `img2webp` is absent or fails. WebP is smaller than GIF here (3.73 MB vs 4.05 MB for the same 36 frames) and carries per-frame durations in milliseconds, so the spec's duration is matched exactly rather than rounded: 3000 ms over 36 frames is 24x83 ms + 12x84 ms. The GIF fallback uses `gm -delay <100/fps>` (8 cs = 80 ms/frame), the only centisecond-resolution option.

The animation budget stays **12 fps / 36 frames / 1200 px** (D12). `animated_svg` is returned as SVG text and is never rasterized.

*Alternatives considered:* GIF as the primary — rejected once `img2webp` was verified. Encoding in the browser or a Node module — rejected as new, unproven code when a maintained tool exists. Inline embedding of the SVG via `md_in_html` — rejected; the article references the SVG as a normal image, which animates in the browser, works with `glightbox`, and survives a lightbox round-trip.

### D5. `motion_clip` is declared, unsupported, and loud

The registry declares it so a request is understood, but the workflow answers `unavailable: no video encoder in this environment` and continues. Enabling it later means adding `ffmpeg` to the n8n image (a `datahub-local-core` change) and one branch that encodes the same frame sequence — which is why the renderer emits frames, not directly an animated image: the frame sequence is the reusable intermediate.

*Alternatives considered:* omit the type entirely — rejected; a silent absence is the failure mode this repo keeps paying for.

### D6. A run record, not an asset store

Each execution writes exactly one row to the `visual_studio_table` DataTable: `RUN_ID` (the execution id, the handle a caller fetches later), `STATUS` (`COMPLETE`/`PARTIAL`/`FAILED`), `REQUEST` (the trigger parameters as JSON), `RESULT` (every asset with status, content and error, as JSON), `ASSET_COUNT` and `ERROR`. The row id is the DataTable's own auto-generated key. This is a **log of what was produced**, not the caller's review state: the workflow reads nothing back to decide what to do, and a re-run with the same parameters writes a second record rather than updating the first, because each run is a distinct event. The table also carries multi-MB base64 payloads — the instance already does exactly that in its `TemporalFiles` table (`dataBase64` column), so the precedent and the Postgres backing exist.

*Alternatives considered:* per-asset rows keyed `<caller-ref>:<type>` (the original design's `article_assets` page, then a DataTable) — rejected twice over: it forced article concepts (`ENTRY_ID`) into a generic workflow and made the studio both a writer and a reader of review state, which belongs to the caller. No record at all, response only — rejected; an HTTP caller that dies mid-response has nothing to recover, and a sub-workflow caller (the article pipeline) cannot hold every asset in one execution indefinitely.

### D7. Content is returned; identity is derived by the caller

The studio returns each asset with its content (image data URL, markup, or text), its format and its status. Filenames (`<post-slug>-<type-id>.<ext>`), repository paths and references into the article are derived by the caller, which owns the slug and the marker contract. The studio MUST NOT invent a path or a URL.

*Alternatives considered:* returning derived filenames — rejected; they break the moment a caller's identity scheme changes, and the studio cannot know the frozen slug.

### D8. The caller owns review, retry and commit

Every Slack gate, the double approval, the retry-with-feedback loop, per-asset review state and the single multi-asset commit are the caller's (`add-content-writer-agent` D4/D5/D9). The studio returns content and never touches a repository. A caller re-renders one rejected asset by re-invoking the studio with that type and the frozen spec.

*Alternatives considered:* the studio owning its own review and commit — rejected; two commit paths to one repository is how a half-published pair happens, and it would split the failure path across two error workflows.

### D9. Freezing is a parameter, not a lookup

The one-content-spec-per-article rule (so a static infographic and its animated counterpart can never disagree) is enforced by the caller, which passes the frozen spec back as `SPEC_JSON`; the studio then uses it verbatim and skips the authoring model call (`if_spec_given` → `spec_from_param`). The supplied spec is validated by the same validator the model's output passes through, so a malformed frozen spec fails loudly with the missing field named. This replaced the original design's freeze lookup, which read the studio's own asset rows — impossible now that the studio is stateless, and cleaner anyway: the caller already knows when a variant has been approved.

*Alternatives considered:* the studio reading prior runs' records to find a frozen spec — rejected; that re-imports caller state (which article? which variant is approved?) through the back door and breaks the "parameters only" contract.

### D10. New workflows are created by an explicit, one-time create path

`scripts/apply_workflow_changes.py` can only edit existing workflows (`PUT /api/v1/workflows/{id}`) and activate them; it cannot create. The studio is new, so the script gained an idempotent `--create` that `POST`s a whole workflow body once, keyed by name, and prints the new id; later edits keep using the existing field-level `PUT` path. This is the documented single exception to "never post a whole exported body", and it exists only for creation.

*Alternatives considered:* manual UI import — rejected as unreproducible; authoring exports without a create path — rejected because the next backup run overwrites them with the live state that lacks them.

### D11. The form trigger uses the instance's proven shape

Form triggers on this instance register both GET and POST under the node's auto-generated `webhookId` path (verified against the live `webhook_entity` rows and the working Enable Banking renewal form). A custom `path` parameter registered the GET route but **not** the POST route — the submission 404'd — so the form trigger ships at typeVersion 2.2 with no `path` and no `responseMode`, pinned `webhookId`, and the default "Form Is Submitted" response. Submission fields are named `field-<index>` (the label is display-only), the form endpoint requires `multipart/form-data`, and n8n's oauth2-proxy middleware requires an `X-Auth-Request-User` header that the public host's proxy adds in production. The form acknowledges immediately; the outcome is fetched from the run record — the API webhook is the synchronous surface.

*Alternatives considered:* `responseMode: lastNode` on the form — rejected; it broke POST registration and would hold a browser open for a multi-minute render. A custom form path — rejected as unregistered for POST (above).

### D12. The animation budget and the request cap are registry values

The registry defaults to **12 fps, 36 frames (3 s) and a 1200px viewport**, and caps a request at **3** asset types (`max_types_per_request`). A type may declare a smaller budget; the renderer never exceeds the registry value. The cap keeps a single request (and its review loop) bounded. Over-cap types are reported as skipped with the reason, never silently dropped.

*Alternatives considered:* lighter (8 fps/24 frames/900px) — rejected as the default because the labelled text is the point of an infographic. Heavier (15 fps/45 frames/1400px) — rejected for size and memory at no readability gain. A hard-coded cap — rejected; it is a data knob.

### D13. The hero survives everything else failing

The static hero is an ordinary requested type — the *caller* decides to request it (the article pipeline always will, first). Given it is requested, the studio guarantees it is produced even when every other asset fails: each asset's render is independent, a failure marks only that asset's record, and the run continues. A run where some but not all assets failed reports `PARTIAL`.

*Alternatives considered:* short-circuiting the run on the first failure — rejected; it would take the hero down with an unrelated animated failure, exactly what the article pipeline must not experience.

## Risks / Trade-offs

- **The response carries multi-MB base64 payloads, and so does the run record.** A 1K-resolution PNG is ~1.4 MB; `RESULT` for a three-asset run can exceed 3 MB in a DataTable cell. → Acceptable: the instance already stores base64 payloads in `TemporalFiles`; the record is the recovery path, not a hot path; and the API webhook is the synchronous surface. If it ever bites, a type can move its content to an out-of-band store without changing the contract.
- **The form trigger cannot return the result synchronously** (D11). → The form acks and the caller fetches by `RUN_ID`; the API webhook covers the synchronous use case.
- **Browser frame capture can be non-deterministic** (fonts not ready, a frame not painted). → Wait for `document.fonts.ready`, drive `currentTime` explicitly, render from a data URL with no network, and keep the declared duration authoritative; a mismatch is an error, not a silently short animation.
- **`gm` memory and output size grow with frames × pixels.** → Cap frames and viewport per type in the registry; animated infographics are small by design.
- **Frame transport can bloat the execution.** → JPEG frames, written through to `~/.n8n-files` promptly rather than all carried in the execution.
- **The Files node cannot write `/tmp`.** → Verified: the renderer uses `~/.n8n-files` and does not disable the security default.
- **The model may return a malformed spec.** → Validate required fields before rendering and fail loudly naming the field; the template assumes a valid spec.
- **`ExecuteCommand` is disabled by default in n8n v2.** → Enabled on this instance (`NODES_EXCLUDE=[]`) with the `webp-converter` extra module; until a fresh instance sets both, no animated asset can be assembled.
- **`DownloadTemplate` reads GitHub `main`.** → Every new prompt/dataset/template file must be committed and pushed before a live run can resolve it; verified the hard way (first run failed with "resource not found").
- **Animated asset size grows with frames × pixels.** → The committed format is WebP (3.73 MB for 36x1200x1500 frames) with a GIF fallback; `img2webp` quality and a smaller registry viewport are the knobs.
- **A caller can desync an approved variant by re-authoring the spec.** → The frozen-spec parameter (D9) is the mechanism; the caller's design (`add-content-writer-agent`) documents when to pass it.

## Migration Plan

1. Add `datasets/visual_types.json`, `templates/infographic.html`, `templates/infographic.svg`, and the per-type prompt files under `agents/n8n/prompts/`; commit and push (DownloadTemplate reads GitHub `main`).
2. Provision `visual_studio_table` with `scripts/setup_data_tables.py --apply`.
3. Build the generic workflow (three triggers → registry → spec/frozen-spec → markup/raster → run record → result), create it live with `--create`, and verify each trigger surface and the run record.
4. Enable `ExecuteCommand` and the `webp-converter` extra module (both landed in `datahub-local-core`); implement frame capture and assembly (D3/D4) and verify the animated WebP plays.
5. Wire the studio into `add-content-writer-agent`'s per-asset review and commit (that change owns the gates, the per-asset state and the single multi-asset commit); exercise reject/retry with the frozen spec passed back.
6. Rollback: deactivate the studio call in the caller; revert any committed asset on `alvsanand`. The run table is append-only history; no rollback needed.

## Open Questions

- The animated frame-capture path (D3/D4) is designed and its pieces verified in-cluster (`img2webp`, browserless, Files-node root) but not yet wired into the workflow; it is the remaining implementation work, tracked in tasks 5.x.
