# Design

## Context

See `proposal.md` for motivation and `specs/visual-studio/spec.md` for the behavior contract. Only the constraints that shape the n8n approach are recorded here, and they were verified in-cluster, not assumed.

- `LinkedIn Image Creator` is the flow to extend: `set_workflow_vars` (models, aspect ratio, resolution) → `download_image_motifs` (`datasets/image_motifs.json`) → `download_image_prompt` (`prompts/linkedin_image_prompt.md`) → art-director LLM → `generate_image` → `set_output` (`omImage` data URL). Prompts and datasets are files fetched by `DownloadTemplate` from `agents/n8n` in the backup repo.
- `generate_image` posts to LiteLLM `POST .../openrouter/images` (model `google/gemini-3.1-flash-image`, `aspect_ratio`, `resolution`); `convert_image` decodes `data[0].b64_json` into binary.
- **`n8n-nodes-puppeteer` v1.5.0** exposes `Get Page Content`, `Get Screenshot` (png/jpeg/webp), `Get PDF`, and **`Run Custom Script`**. It connects to browserless at `ws://datahub-local-core-automation-n8n-chromium:3000?token=...` (`download_content`'s `puppeteer` node shows the exact form).
- **browserless/chromium v2.56.7** serves `screenshot`/`pdf`/`content`/`scrape` over HTTP and a Puppeteer/CDP WebSocket; it bundles Playwright's `ffmpeg-linux` inside its own image, but that binary is not reachable from n8n.
- **GraphicsMagick 1.3.47** runs in the n8n image with GIF and WebP delegates. Verified in-cluster on 2026-09-27: `gm convert -list format` reports `GIF P rw+` (multi-image) but `WEBP P rw-` (single-image), and `gm convert -delay 8 -loop 0 f_*.jpg out.webp` from 36 frames produced a **one-frame 3.7 KiB** WebP while the same input produced a **36-frame GIF**. A 36-frame GIF animates correctly. No `img2webp`, `webpmux`, `cwebp`, `gif2webp` or `ffmpeg` exists in the image. So GraphicsMagick here can assemble animated **GIF only** (the fallback in D4).
- **`ExecuteCommand` is disabled by default in n8n v2, and is enabled by a `datahub-local-core` change (decided).** Verified in-cluster on 2026-09-27: activating a workflow with `n8n-nodes-base.executeCommand` fails with `Unrecognized node type` (`dist/modules/breaking-changes/rules/v2/disabled-nodes.rule.js` lists it; re-enable with `NODES_EXCLUDE=[]`). A `Code` node cannot substitute (`require('child_process')` is disallowed). The instance therefore gains `NODES_EXCLUDE=[]`, and `img2webp` for animated WebP comes from the `webp-converter` npm package, installed by n8n's `extra_modules` boot step (globally, into `/usr/local/lib/node_modules/webp-converter/bin/libwebp_linux/bin`) — **two `datahub-local-core` prerequisites this change must not assume are absent.** Verified 2026-09-27: `webp-converter` bundles libwebp 1.6.0 `cwebp`/`img2webp`/`gif2webp` that run on this hardened-Alpine image, and `img2webp -loop 0 -d 83 f_*.jpg -o out.webp` turned 36 captured JPEG frames into a 36-frame animated WebP (3.73 MB, 1200x1500, loop 0, JPEG input accepted).
- The n8n image also contains `EditImage`, `Files` (read/write from disk, rooted at `/home/node`) and `Code` nodes. `EditImage` cannot assemble an animation.
- n8n is **2.41.3 on Postgres** (verified live 2026-09-27), with a `DataTable` node available. The `Read/Write Files from Disk` node is confined to `~/.n8n-files` (`N8N_BLOCK_FILE_ACCESS_TO_N8N_FILES` defaults to true and is not overridden here); `/tmp` is reachable by `ExecuteCommand` but not by the Files node. The renderer therefore writes frames under `~/.n8n-files`, never `/tmp` (G22).
- `add-content-writer-agent` plans the article pipeline, its Slack `sendAndWait` review, and its GitHub commit step. It has dropped the singular `IMAGE_*` columns in favour of this change's `article_assets` page (A3), so the asset set here is the one source of truth and the article workflow owns the gates and the commit (D9).
- Blog conventions are as recorded in `add-content-writer-agent/design.md`: posts under `docs/blog/posts/`, images under `docs/img/`, referenced `/img/<file>`, plugin-derived URL. The blog emits **no `og:image`** (the Material `social` plugin is not configured, and zero `og:` tags appear in the built site), so the required static hero is the article's *first image* — the thing platforms preview by scraping the page — not an `og:image` tag. Enabling the `social` plugin is an optional `alvsanand` cross-repo follow-up, out of scope here.

## Goals / Non-Goals

**Goals:**
- One workflow, many output types, driven by a registry file rather than by branches in the workflow.
- Animation with no new service and no video model: browser timeline → frames → GraphicsMagick.
- Model output is data; markup is deterministic; labels/values agree across a static and an animated variant.
- Per-asset review that matches the Slack UX the reviewer already uses.

**Non-Goals:**
- True video (`motion_clip`). Declared, reported unavailable; it needs `ffmpeg`, which is not in the n8n image.
- Changing `linked_in_post_creator`, `linked_in_image_creator` or the live LinkedIn lane.
- A Sympozium agent, an MCP server, or any cluster change.
- Free-form model-authored HTML/SVG (rejected in D2).
- Committing intermediate frames or browser artifacts.

## Decisions

### D1. A registry file is the type axis

`datasets/visual_types.json` declares each type: `{id, author, template, render, format, aspect, budget}`. The workflow reads it, filters to the requested types, and routes each through its declared render mode. Adding a type is a data change.

*Alternatives considered:* a separate sub-workflow per type — rejected; it multiplies workflows and hides the common authoring stage. Hard-coded `switch` branches — rejected; the registry is the repo's existing dataset pattern (`image_motifs.json`). Having the registry drive static-raster art direction too — rejected (A6); the tuned `image_motifs.json`/`HOOK_TREATMENT` axis stays for the raster path, and the registry governs structure, render mode and format only, so it can change without retuning the art director.

### D2. Two-stage authoring: model emits a content spec, code emits markup

Stage 1 asks the model for a typed JSON spec: `{title, blocks:[{label, value}], accent, motion:{kind, durationMs}, alt}`. Stage 2 is a Code node that fills a template file (`templates/infographic.html` or `templates/infographic.svg`) from the spec. Static raster types keep the existing art-director → image-model path, but its prompt is derived from the article plus the spec so the raster matches the markup.

*Alternatives considered:* model writes HTML/SVG directly — rejected; this is the Mermaid/Kroki lesson the repo already paid for, and it makes static and animated variants diverge. A schema-less free string — rejected; a missing field must fail loudly (spec requirement).

### D3. Animation is frame-stepped from the browser, then assembled

The markup is rendered from a `data:text/html;base64,...` URL at a fixed viewport and device scale. A Puppeteer **custom script** waits for `document.fonts.ready`, pauses every animation, and for `i` in `0..N-1` sets each animation's `currentTime` to `i * 1000/fps`, awaits a frame, and screenshots to **JPEG** (smaller than PNG; `gm` re-encodes to GIF anyway). Frames are written under `~/.n8n-files/<execution>/<asset>/` with the `Files` node — the only root that node may write (G22) — and each frame is written through promptly so the execution does not carry all of them at once (G23). `ExecuteCommand` runs `img2webp -loop 0 -d <ms> <frames> -o <out>` (the GIF fallback is `gm convert -delay <100/fps> -loop 0 <frames> <out>`) against the same directory; the result is read back as binary. `ExecuteCommand` is disabled by default in n8n v2 and is enabled with `NODES_EXCLUDE=[]`, and `img2webp` comes from the `webp-converter` extra module — both `datahub-local-core` changes (Impact). The instance's binary-data mode is checked before building, since large in-execution binaries are the failure this design avoids.

Frame count, fps and duration come from the type and spec, never from wall-clock recording, so a run is reproducible and a re-render is comparable.

*Alternatives considered:* CDP screencast / wall-clock recording — rejected as non-deterministic and heavier on browserless. Playwright video via the chromium pod's ffmpeg — rejected; not reachable from n8n and would be a new client. A video model — rejected; none is configured and infographic text mangles. `/tmp` — rejected; the Files node cannot write it without disabling a security default instance-wide.

### D4. Animated WebP is the committed format, GIF the fallback

The committed animated asset is **WebP**, encoded with libwebp's `img2webp` from the captured frames. GraphicsMagick in this image cannot write an animated WebP (`WEBP P rw-` is single-image; verified 2026-09-27), so the assembler is `img2webp`, not `gm`; `gm` is the **GIF fallback** when `img2webp` is absent or fails. Both run through `ExecuteCommand`, which the instance enables (`NODES_EXCLUDE=[]`), and `img2webp` comes from the `webp-converter` package installed via n8n's `extra_modules` — both `datahub-local-core` changes, recorded in Impact. WebP is smaller than GIF here (3.73 MB vs 4.05 MB for the same 36 frames) and carries per-frame durations in milliseconds, so the spec's duration is matched exactly rather than rounded.

The animation budget stays **12 fps / 36 frames / 1200 px** (D13). The spec's `motion.durationMs` sets the animation timeline the frames are sampled from **and** the playback duration: `img2webp` takes integer milliseconds per frame, so the renderer distributes the remainder (e.g. 3000 ms over 36 frames is 24x83 ms + 12x84 ms) and duration matches the spec to the millisecond. The GIF fallback uses `gm -delay <100/fps>` (8 cs = 80 ms/frame, 2.88 s for 36 frames), the only centisecond-resolution option. `animated_svg` is committed as SVG text and is not rasterized.

*Alternatives considered:* GIF as the committed format — rejected once `img2webp` was verified, because WebP is smaller and matches duration exactly; using `gm` for WebP — impossible (single-image output); encoding in the browser or a Node module — rejected as new, unproven code when a maintained tool exists; a smaller viewport or colour reduction — held as a registry knob, not applied now. Inline embedding of the SVG via `md_in_html` — rejected (A5); the article references the SVG as a normal image, which animates in the browser, works with `glightbox`, and survives a lightbox round-trip. Committing only the rendered binary — rejected (A4); the HTML/SVG source is committed beside the rendered asset as `<frozen-slug>-<type-id>.html`, so a re-render is possible and the source is diffable.

### D5. `motion_clip` is declared, unsupported, and loud

The registry declares it so a request is understood, but the workflow answers `unavailable: no video encoder in this environment` and continues. Enabling it later means adding `ffmpeg` to the n8n image (a `datahub-local-core` change) and one branch that encodes the same frame sequence — which is why the renderer emits frames, not directly an animated image: the frame sequence is the reusable intermediate.

*Alternatives considered:* omit the type entirely — rejected; a silent absence is the failure mode this repo keeps paying for.

### D6. A child `article_assets` page holds the set

One row per artifact: `ENTRY_ID, ASSET_ID, ASSET_TYPE, RENDER_MODE, FORMAT, STATUS, ROUND, FEEDBACK, SPEC_JSON, PROMPT, PATH, DURATION_MS, FRAME_COUNT, WIDTH, HEIGHT, URL, ERROR, UPDATE_DATE`. `ASSET_ID` is the deterministic composite `ENTRY_ID:ASSET_TYPE`, and the upsert matches on it, because n8n's Sheets update matches a single column and "article + type" is two (G24). A non-terminal asset row is cancelled with its entry, so no orphan survives a cancel (G31). This replaces the singular `IMAGE_*` columns from `add-content-writer-agent`; every asset is reviewed and retried independently and the published state is per row.

*Alternatives considered:* an `ASSETS` JSON column on `article_queue` — rejected; per-asset updates and concurrency become read-modify-write on one cell, and Sheets cell limits bite. Matching the upsert on `ENTRY_ID` alone — rejected; one row per type needs a per-type key.

### D7. File identity is derived, not chosen

Asset filename is `<post-slug>-<type-id>.<ext>` under `docs/img/`, so it is deterministic and collision-checked against the repo before commit. The static hero keeps the existing hero path convention so the article's first static image is stable.

*Alternatives considered:* random or timestamped names — rejected; they break idempotency and re-render comparison.

### D8. Reuse the article pipeline's review and publish; do not fork them

Each asset gets the same `sendAndWait` double approval and retry form already used for article and image. Publication reuses the article workflow's GitHub Git Data commit, extended to the asset list. If the studio is run standalone, it produces and reviews assets but the commit is the article workflow's job.

*Alternatives considered:* give the studio its own publisher — rejected; two commit paths to one repository is how a half-published pair happens.

### D9. The article workflow owns the gates and the commit; the studio is a sub-workflow

The studio is invoked with `(ENTRY_ID, ARTICLE_TEXT, ASSET_TYPES)` and returns the asset set and its per-asset outcomes. It runs no review gate and performs no commit. `Article Content Writer` owns every Slack gate and the single multi-asset commit, so there is exactly one failure path and one writer to the repository.

*Alternatives considered:* the studio owning its own review and commit — rejected; it would split the failure path across two error workflows and give the repository two writers.

### D10. New workflows are created by an explicit, one-time create path

`scripts/apply_workflow_changes.py` can only edit existing workflows (`PUT /api/v1/workflows/{id}`) and activate them; it cannot create. The studio and its error path are new, so the script gains an idempotent `--create` that `POST`s a whole workflow body once, keyed by name, and prints the new id; later edits keep using the existing field-level `PUT` path. This is the documented single exception to "never post a whole exported body", and it exists only for creation.

*Alternatives considered:* manual UI import — rejected as unreproducible; authoring exports without a create path — rejected because the next backup run overwrites them with the live state that lacks them.

### D11. One content spec per article, frozen once any variant is approved

There is one content spec per article and every variant derives from it. Once any variant is approved, a sibling's retry may change styling or motion only, never the spec's title, labels or values, so an approved static infographic cannot drift from its animated counterpart. A change that genuinely needs different data is a new article round and invalidates every variant together.

*Alternatives considered:* a per-asset spec — rejected; it is what lets the two variants disagree, which is the failure the shared-spec requirement exists to prevent.

### D12. Placement and identity come from the article, not the studio

The studio returns files; the article workflow inserts the references. Placement follows the article's marker contract (`<!-- asset:<type> -->`, default position when missing) and the filenames bind to the article's slug, which is frozen at first draft. The studio MUST NOT invent a path or a URL.

*Alternatives considered:* the studio inserting its own references — rejected; it does not own the article and cannot know the final slug after a retry.

### D13. Animation budget and asset cap

The registry defaults to **12 fps, 36 frames (3 s) and a 1200px viewport**, and an article may request at most **3** asset types (B1+B2). These are registry values, so a type may declare a smaller budget, and neither is baked into the renderer. The cap keeps the review loop bounded.

*Alternatives considered:* lighter (8 fps/24 frames/900px) — rejected as the default because the labelled text is the point of an infographic and needs resolution; heavier (15 fps/45 frames/1400px) — rejected for size and `gm` memory at no readability gain.

### D14. The studio inherits the article workflow's operational rules

It reviews in the same `#workflows` channel, is triggered by the article workflow rather than by its own schedule, reuses the existing GitHub credential (through the article workflow's commit), and relies on the article workflow's single-flight claim and resumable review (`add-content-writer-agent` D13/D14) rather than implementing its own. The studio is a called sub-workflow; it never claims an entry and never commits.

*Alternatives considered:* giving the studio its own schedule, channel and credential — rejected; it would duplicate configuration and create a second writer and a second place to watch.

### D15. Column ownership on `article_assets` is split by writer

The studio writes everything it knows about an asset row (`ASSET_*` state, `ROUND`, `FEEDBACK`, `SPEC_JSON`, `PROMPT`, `FORMAT`, `ERROR`, `UPDATE_DATE`). The article workflow writes only what it owns — `PATH`, `URL` and the commit reference — and nothing else. No cell is read-modify-written from both sides, which is the failure mode of sharing a row without an assignment rule (G19).

*Alternatives considered:* the article workflow owning the whole page — rejected; then the review loop would be reading a workbook the article workflow is also writing. A single owner for everything — rejected; the studio learns asset state no one else can.

## Risks / Trade-offs

- **Browser frame capture can be non-deterministic** (fonts not ready, a frame not painted). → Wait for `document.fonts.ready`, drive `currentTime` explicitly, render from a data URL with no network, and keep the asset's declared duration authoritative; a mismatch is an error, not a silently short animation.
- **`gm` memory and output size grow with frames × pixels.** → Cap frames and viewport per type in the registry; animated infographics are small by design.
- **Frame transport can bloat the execution.** → JPEG frames, written through to `~/.n8n-files` promptly rather than all carried in the execution, and the instance's binary-data mode is checked first (`N8N_DEFAULT_BINARY_DATA_MODE` is unset here; S3 storage credentials are present). This is the failure the write-through design avoids.
- **The Files node cannot write `/tmp`.** → Verified: `N8N_BLOCK_FILE_ACCESS_TO_N8N_FILES` defaults to true and is not overridden; the renderer uses `~/.n8n-files` and does not disable the security default.
- **Animated asset size grows with frames × pixels.** → The committed format is WebP (3.73 MB for 36x1200x1500 frames) with a GIF fallback; `img2webp` quality/`-lossy` and a smaller registry viewport are the knobs if it ever bites.
- **The model may return a malformed spec.** → Validate required fields before rendering and fail loudly (spec requirement); the template assumes a valid spec.
- **`ExecuteCommand` is disabled by default in n8n v2.** → Enabling it (`NODES_EXCLUDE=[]`) and installing the `webp-converter` extra module are `datahub-local-core` prerequisites; until they land, no animated asset can be assembled (task 5.1 verifies both).
- **Review fatigue across a set.** → Cap requested types per article (three is a sensible ceiling) and group all assets of one article into one Slack thread.
- **Animated SVG in MkDocs.** → Commit and reference it as an image (`<img>`/`![]`); it animates in the browser, shows one frame in Slack. Inline embedding via `md_in_html` is an option, not a requirement.
- **Two changes meeting at one pipeline** (`add-content-writer-agent` and this one). → The studio lands first; the asset set is the interface, and the article workflow owns the gates and the commit (D9).
- **A sibling retry can desync an approved variant.** → One spec per article, frozen once any variant is approved; a post-approval retry changes styling or motion only (D11).
- **A title edit or a missing marker can orphan or drop an asset.** → Filenames bind to the slug frozen at first draft, and a missing marker places the asset at a default position rather than dropping it (D12, and `add-content-writer-agent` D11/D12).
- **The create path is a new capability on the apply script.** → Scope `--create` to creation only, idempotent by name, print the new id, prove it with a throwaway workflow, and leave a same-named workflow untouched (D10).

## Migration Plan

1. Add `datasets/visual_types.json`, `templates/infographic.html`, `templates/infographic.svg`, and the per-type prompt files under `agents/n8n/prompts/`.
2. Add the `article_assets` page with the D6 columns.
3. Build the Visual Studio sub-workflow; enable `ExecuteCommand` and install the `webp-converter` extra module (both `datahub-local-core`, see Open Questions); set frames to write under `~/.n8n-files/<execution>/<asset>/`; render each supported type from the manual trigger against a fixed spec and confirm the animated WebP plays.
4. Wire the studio into the article pipeline's per-asset review and the commit step; exercise reject/retry on one asset while others stay approved and confirm the approved sibling's spec did not change and the cancelled entry retires its asset rows.
5. Extend `scripts/apply_workflow_changes.py` with the idempotent `--create` (D10), verify it with a throwaway workflow, then create the studio workflow live; later edits keep using the field-level `PUT`. Wire `settings.errorWorkflow`.
6. Rollback: deactivate the studio call in the article workflow; revert any committed asset on `alvsanand`. No cluster state is involved.
7. Archive this change before `add-content-writer-agent`, so that change's reference to the `visual-studio` capability resolves (G29).

## Open Questions

- **Two `datahub-local-core` prerequisites (decided, not yet landed):** set `NODES_EXCLUDE=[]` so `ExecuteCommand` runs, and set `custom.extra_modules: webp-converter` so the libwebp CLIs (`img2webp`) are installed at boot. (The `extra_modules` installer itself needed a one-line fix: `npm add` in the n8n tree fails on this image, so it installs globally.) Until both land, task 5.1 stays blocked and no animated asset is producible.
- The instance's binary-data mode, which determines whether large frame payloads need extra care before the renderer is built ([UNVERIFIED]; see the frame-transport risk).
