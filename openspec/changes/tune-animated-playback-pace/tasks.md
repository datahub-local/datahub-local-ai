# Tasks

## 1. Registry and mechanism

- [x] 1.1 Add `durationMs: 9000` to `diagram_animated_linkedin` in `agents/n8n/datasets/visual_types.json`; verify the file parses and no other type's fields change. Done; note the registry is fetched from GitHub `main` at runtime, so the declared pace is live only once pushed (see 3.2).
- [x] 1.2 Carry the type's pace in `parse_registry` (`DURATION_MS: Number(t.durationMs) || 0`) in both copies of `visual_studio.workflow.json`
- [x] 1.3 In `merge_assets`, set the animated duration to `type.DURATION_MS || spec.motion.durationMs` (clamped `1000..20000`) and pass that same `dur` into `buildMarkup` so the CSS timeline matches the capture window; verified by the offline test
- [x] 1.4 Raise the duration clamp to `1000..20000` in `capture_frames`, `build_assemble` and `buildMarkup`
- [x] 1.5 Widen the `motion.durationMs` range in `spec_from_param` and `parse_spec` to `2000..12000` in both copies
- [x] 1.6 Update rule 6 of `agents/n8n/prompts/visual_spec.md` to the new range

## 2. Tests

- [x] 2.1 Add `agents/n8n/scripts/test_visual_studio_animation_pace.py` over both export copies and the registry; verified it fails against the pre-change export (no `DURATION_MS` override, no 20000 ceiling, no `durationMs`)
- [x] 2.2 `uv run -- pytest agents/n8n/scripts/ -q` → 157 passed; render suite 44 passed

## 3. Apply and verify live

- [x] 3.1 Applied the six node fields to `Visual Studio` with `--require-edge` guards (`merge_assets>if_video`, `spec_ready>download_html_template`, `if_animated>mkdir_frames`), republished, and re-read: `active`, 48 nodes in both copies, `merge_assets` override present
- [ ] 3.2 Run `Visual Studio Test` for `diagram_animated_linkedin` with a spec asking `motion.durationMs: 3000` and confirm the asset is ~9000 ms from the **type's** declared pace. **Blocked on pushing `visual_types.json` to GitHub `main`** (the live `DownloadTemplate` reads main; the local edit is not live). The raised ceiling itself is verified live: a spec asking 9000/12000 produced 9.000 s / 12.000 s GIFs.
- [x] 3.3 Generated comparison samples (see below) for the other types and the LinkedIn type; recorded in `~/visual-studio-samples/pace/`

## Samples (in `~/visual-studio-samples/pace/`)

| File | Frames | Size | Measured duration |
| ---- | ------ | ---- | ----------------- |
| `linkedin-3000ms.gif` | 24 | 1080×1350 | 3.000 s (before) |
| `linkedin-9000ms.gif` | 24 | 1080×1350 | 9.000 s (3×) |
| `linkedin-12000ms.gif` | 24 | 1080×1350 | 12.000 s (4×) |
| `webp-3000ms.webp` | 36 | 1200×1500 | 3.000 s (before) |
| `webp-6000ms.webp` | 36 | 1200×1500 | 6.000 s |
| `webp-9000ms.webp` | 36 | 1200×1500 | 9.000 s |
| `webp-12000ms.webp` | 36 | 1200×1500 | 12.000 s |
| `video-3000ms.mp4` | 90 | 1080×1350 | 3.000 s (before) |
| `video-9000ms.mp4` | 270 | 1080×1350 | 9.000 s |

## 4. Record

- [ ] 4.1 Update the `#### LinkedIn post media` section of `AGENTS.md` to name the type's declared pace and the raised ceiling
