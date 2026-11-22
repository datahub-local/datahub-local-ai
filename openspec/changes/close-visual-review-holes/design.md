# Design

## Context

Execution 17510 (2026-11-22) is the gate finding for this change: two authoring runs, three
correction turns each, `VERDICT: fix` at the budget, `STATUS: COMPLETE`, and a human retry then
cancel. The defects were visible to the critic (arrows, a missing head, copy overload) and the
loop still shipped them, so the defect is in the review's *state*, not only in its prompt.

The framework already provides the deterministic half: `hyperframes check --json
--at-transitions` returns `{ok, lint, runtime, layout, motion, contrast, craft, audio, hdr,
snapshots}` with a selector, `data-*` identity, bbox and sample time on every finding; craft
warnings include `line_unread`, `dead_stretch`, `text_below_floor` and `first_frame_empty`. The
adapter owns the render and the artifact, so it is the only place that can run these against the
delivered bytes.

## Decisions

### D1 — Two gates, in this order

The deterministic gate runs on the artifact the adapter produced; the critic runs on what the
gate cannot decide. A check error becomes a ledger finding with `source: "check"` and severity 1, a
layout/motion/contrast warning becomes severity 2, and four craft warnings become severity 2:
`line_unread`, `text_below_floor`, `dead_stretch` and `first_frame_empty`. The copy budget is
therefore measured, not prompted: on `lips-60` — the render a human cancelled for "too much text"
— the live 0.9.1 check reports six `line_unread` lines and `100 text elements under the 28 px
floor`, which is the rejection reason as data.
A check that could not run is `{ran: false, reason}` on the asset; for an animated type that is a
review finding (`MOTION_GATE: absent`), not a clean result.

*Rejected:* running the critic first and using it to find container/layout defects. It is slower,
non-deterministic, and blind to the frame between samples.

### D2 — A ledger, not a verdict

Findings cross turns as:

```json
[{"id":"F1","severity":1,"where":"scene 05","what":"the connector has no head",
  "fix":"draw the head on the Agent edge","seen":2,"source":"critic"}]
```

The critic is given the open ledger and must answer:

```json
{"verdict":"fix","resolved":["F2"],
 "findings":[{"id":"F1","severity":1,"where":"...","what":"...","fix":"..."}]}
```

- `resolved` names ids that are no longer present.
- A re-reported defect reuses its id; a new one has `id: null` and is allocated `F<n>`.
- An open id that is neither resolved nor re-reported stays open and its `seen` does not increase
  (the critic was silent, not the composer).
- `seen >= 2` means the finding survived a correction turn: `stalled`. The loop does not spend
  another turn on it, and the asset is `NEEDS_REVIEW` with `STALLED` naming it.

*Rejected:* comparing free-text findings across rounds. The composer and critic both paraphrase,
so similarity is a guess; ids make the comparison exact.

### D3 — Unreadable blocks

`parse_verdict` currently defaults to `verdict: "ok"`. It becomes `verdict: "unread"`,
`NEEDS_REVIEW: true`, `RETRY: false`. A parsable object with no usable `verdict` and no findings
is unread too; "we could not tell what it said" is the same state as silence. The spec already
required this (`visual-studio/spec.md`, "the review is recorded as not run or as unread rather
than as a pass"); the code is the bug.

### D3a — No invented ledger

The critic is shown the open ids. When the review gives it none, it MUST NOT invent one: a live
evaluation had it answer `resolved: ["F1","F2"]` with `id: "F3"` on a first-round render with no
ledger. The prompt says the ledger is empty, `resolved` is `[]`, and every finding has `id: null`.

### D4 — The critic ranks

`severity` is 1 (unreadable / blocks the meaning), 2 (visible defect), 3 (polish). The correction
brief lists findings sorted by `(severity, id)`, so the composer fixes the cheap, meaning-breaking
defects first. 17510 spent its cycles on arrow geometry while the human's rejection reason was
copy overload.

### D5 — Stills by scene

`ffmpeg -vf "select='gt(scene,0.3)',showinfo"` gives cut times. Scenes are the intervals between
cuts; each scene contributes one still taken at its midpoint, plus two frames straddling each cut
(capped at 12 stills), plus the settled frame. `SCENES_SEEN` and `SCENES_COVERED` are recorded.
A uniform grid dense enough for the duration — `ceil(duration / 2.5)` samples, at least 8 and at
most the cap — is the fallback when detection finds no cut. The live 17510 render is one continuous
animation with no hard cut (`select=gt(scene,0.3)` selects nothing), so a uniform grid of 8 across
30 s was exactly the coverage hole this closes.

A clip also carries one **contact sheet** at 1 frame per second, sent before the detailed stills.
It answers "what plays between the stills" for one image (~55-95 KB, 6x5 tiles at 213 px) instead
of 30 full stills, which would cost roughly 64k prompt tokens and dilute attention across the
call. Measured on the 12 s `sketch-16955` render: its sheet shows a near-empty transition at
t=2 s that no settled still contained; on the 31 s `lips-60` render it shows the `0` counter and
the two-sentence closing frame. The detailed stills remain the only evidence for geometry and
copy, because the sheet's small text is not reliably readable.

*Rejected:* denser uniform sampling. It costs more images for the same blind spots; cuts are the
structure the content actually has.

### D6 — Connectors as data

`connectors.json` beside the composition:

```json
{"connectors":[{"id":"f-w3","from":"db","to":"kafka","head":true}]}
```

`runtime/connectors.js` (staged next to `gsap.min.js`, and kept out of `vendor/` because it is first-party) exposes `HFConnectors.draw(list, {duration})`:
it computes each line from the live `getBoundingClientRect()` of `from` and `to`, draws the line
and a head inside one SVG overlay, tags them `data-connector` / `data-connector-head`, and sets
`document.documentElement.dataset.hfConnectors = "ok"` when every declaration resolved, or
`"error:<ids>"` when one did not. The adapter runs Chromium over the settled frame and reads that
attribute. A `diagram` brief with `connectors.json` absent, or with `data-hf-connectors` reporting
an unresolved id, is a finding (severity 1), so the helper is not optional.

This makes "the head points at nothing" unrepresentable: the head is placed on the target box's
edge from the target's own rect.

*Rejected:* a validator that parses hand-written SVG coordinates. It can only re-check the
composer's arithmetic, which is what failed in 17510.

### D7 — One decode pass for motion

`ffmpeg -vf freezedetect=n=0.003:d=0.5,blackdetect=d=0.1:pix_th=0.02:pic_th=0.99 -f null -` gives freeze and
black spans; `scdet=threshold=10` gives cuts (`lavfi.scd.time`). The black threshold is 2%, not the 10% default: at 10% the dark brand surface of `lips-60` reports seven "black" spans that are the background, while 2% reports none on both real clips and still catches a synthetic true-black second. They are reported as `signals`:
`{freeze:[{start,end}], black:[{start,end}], cuts:[t], scenes:[{start,end}]}`. Only three become
findings: a black span at frame 0 (severity 1), any other black span of 0.3 s or more (severity 2),
and a freeze that reaches the end of the clip (severity 2). Mid-clip holds are not findings — the
motion rules allow a scene to hold long enough to read, and the 17510 session's clip has many 0.5-1.3 s
holds that are intentional.

### D8 — What is not automated

Arrow direction (database into log must not point back), whether a claim traces to the content,
and whether a scene reads at phone width stay with the critic. The partition follows VBench-2.0:
detectors for perceptual facts, a model for semantics.

## Interfaces

### Adapter response (additive)

```json
{
  "check": {"ran": true, "ok": false, "reason": "",
            "counts": {"error": 2, "warning": 1, "info": 0},
            "findings": [{"code":"container_overflow","severity":"warning",
                          "section":"layout","selector":"#t-grid","message":"...",
                          "fixHint":"...","time":1.4,"bbox":{"x":0,"y":0,"w":0,"h":0}}]},
  "signals": {"freeze": [], "black": [], "cuts": [3.6, 8.4],
              "scenes": [{"start":0,"end":3.6}], "scenesSeen": 7, "scenesCovered": 7},
  "connectors": {"declared": 9, "drawn": 9, "errors": []}
}
```

`check.ran === false` also sets `motionGate: "absent"` on the asset. The check's flags are pinned
to what the installed 0.9.1 binary accepts (`--json --at-transitions --timeout=45000`); a flag
from a newer release makes the whole gate a usage error, which the live pod measured as
`Unknown flag: --cache`. `findings` is capped at 25,
errors and warnings first, so a pathological report cannot bloat the execution record.

### Asset fields (additive)

`CHECK`, `CHECK_OK`, `CHECK_REASON`, `SIGNALS`, `CONNECTORS`, `OPEN_FINDINGS`, `STALLED`,
`VERDICT`, `NEEDS_REVIEW`, `REVIEW`, `SCENES`, `SCENES_SEEN`, `MOTION_GATE`.

### Ledger algorithm (`parse_verdict`)

```
prev = JSON.parse(asset.OPEN_FINDINGS || "[]")
check = asset.CHECK.findings -> [{id:"C<code>-<selector>", severity, source:"check", seen:prev.seen+1}]
resolved = new Set(answer.resolved)
reported = Map(answer.findings.filter(id != null) by id)
next = []
for f in prev:
  if resolved.has(f.id): continue
  if reported.has(f.id): next.push({...f, ...reported.get(f.id), seen: f.seen + 1})
  else next.push(f)                      // silent: still open, not seen again
next += new findings (id null) -> F<max+1>, seen = 1
next += check (replacing a same-id previous entry)
open = dedup(next by where+what for new ids)
RETRY = open.some(f => f.seen === 1) && round < cycles
// A check error that persists after a correction stalls like a critic finding:
// deterministic or not, repeating the turn has already been shown not to fix it.
NEEDS_REVIEW = open.length > 0 || unreadable
STALLED = open.filter(f => f.seen >= 2).map(f => f.id)
```

### Correction brief (`review_feedback`)

```
Fix these in this order. Re-check each against the rendered result before reporting:
1. [F1 severity 1] where: ... | what: ... | fix: ...
...
Open findings not listed here are still open; do not regress them.
```

## Risks

- **A `stalled` rule can stop early on a finding the composer could have fixed.** Mitigated by
  severity and by the human gate; the record names the stalled id so the next run can carry it.
- **Cut detection is approximate** on a clip with a continuous camera move (few hard cuts). The
  uniform fallback covers it, and `SCENES_SEEN` is recorded rather than assumed.
- **`check` adds ~30-60 s per turn** and launches Chrome. It runs once per delivered artifact, not
  per revision; the composer's own `lint` stays the fast loop.
- **The critic is not deterministic.** The same stills at `temperature: 0` answered `fix` and `ok`
  on two runs of the `sketch-clean` case, so the eval scores at least two samples and the pipeline
  should treat a single `ok` as weak evidence. A stable critic may need two calls or a trained
  judge; this change measures the variance rather than assuming it away.
- **The connector helper changes how diagrams are authored.** The brief must state it plainly, and
  an SVG-only type cannot use it; that gap is reported as `connectors.declared == 0` with
  `MOTION_GATE: absent`, not hidden.

## Open questions

- Should `check` replace the composer's own `check` run, or run in addition to it? This change
  keeps both: the composer's run is its editing loop, the adapter's is the record.
- For a standalone SVG, `check` applies to HTML compositions only. Until the SVG is authored
  inside `index.html` and extracted, SVG motion is ungated and the asset says so.

## Appendix — first critic baseline (2026-11-22)

Model `opencode-go/minimax-m3`, prompt `prompts/visual_review_composition.md` with the ledger
protocol and the contact-sheet note, 2 samples per case, stills plus a 1 fps sheet where the
medium has a timeline. Run through `scripts/score_review.mjs` against the live LiteLLM gateway.

| Case | Verdict | Finding |
| --- | --- | --- |
| `lips60-copy` | 2/2 | 2/2 |
| `connector-head` | 2/2 | 2/2 |
| `sketch-clean` | 2/2 | 2/2 |
| `sketch-svg-clean` | 2/2 | 2/2 |

TPR 4/4, finding recall 8/8, unparsed 0%, TNR `n/a` (no human-verified clean negative yet).
Before the sheet, at one sample, the same four cases also all returned `fix`, but the matcher
scored 1/4 because it matched literal phrases, and `sketch-clean` returned `fix` then `ok` on
two runs of the same stills. With the sheet, both samples agreed on all four; n=4, so this is
evidence, not proof. The two sketch cases passed the old critic and are defective by eye, which
is why they are labelled from the frames rather than from the old verdict.
