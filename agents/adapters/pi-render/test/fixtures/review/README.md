# Critic eval corpus

`scripts/score_review.mjs` runs the studio's critic prompt over a labelled corpus and reports
verdict accuracy and finding recall (TPR/TNR), the unparsed rate, and the spread across samples.
It is a hand-run tool, not CI: it needs the gateway.

```
REVIEW_BASE_URL=https://gateway/v1 REVIEW_API_KEY=... REVIEW_MODEL=opencode-go/minimax-m3 \
  node scripts/score_review.mjs --cases test/fixtures/review --samples 2
```

`cases.json`:

```json
[
  {
    "name": "17523-connector-head",
    "brief": "the authoring brief, verbatim",
    "sheet": "connector-head/sheet.jpg",
    "stills": ["connector-head/review-5.jpg", "connector-head/review-final.jpg"],
    "expected": {
      "verdict": "fix",
      "findings": [{"what": "no arrowhead; bare line; connector has no head"}]
    },
    "note": "execution 17523, session lips-j5n6da"
  }
]
```

`sheet` is optional and is only used for a clip: one frame per second, row-major, sent before the
detailed stills. `expected.findings[].what` is a semicolon-separated list of short keywords; any
one appearing in the answer's findings counts as a hit, after punctuation and case are removed.

## Present cases

| Case | Expected | Source |
| --- | --- | --- |
| `lips60-copy` | fix: a chip collision, the `0` counter, or a second closing sentence | execution 17296, `lips-60` |
| `connector-head` | fix: the Serving -> Agent connector has no arrowhead | execution 17523, `lips-j5n6da` |
| `sketch-clean` | fix: a near-empty settled frame, or a caption crossing the gold border | execution 16955 |
| `sketch-svg-clean` | fix: an arrow head in empty space, or a caption on the silver box | execution 16965 |

The last two **passed the old critic** and are not clean: the first has a nearly empty frame at
still 2, the second has the gold arrow ending in empty space. They are labelled from the frames,
not from the old verdict. That is the point — the old review was a false-negative machine.

## Cases still to add

| Case | What it should catch | Source |
| --- | --- | --- |
| `blank-first-frame` | the card's first frame is one colour | run 13770, `launch_card` |
| `wrong-container` | a 16:9 brief served at 1080x1350 / 3 s | run 13785, `tiles_wide` |
| `seven-scene-miss` | a defect in a scene the old three stills never saw | 2026-11-21 |
| `panel-overlap` | two panels touching or overlapping | 2026-11-17 |
| `clean-render` | no finding on a **human-verified** clean render | not yet found |

There is no verified clean negative yet. Every render the old critic passed has turned out to
carry a real defect, so TNR is `n/a` until one is produced and checked by eye.

A prompt edit is accepted only if it does not lower verdict accuracy or finding recall on this
corpus, across at least two samples (the critic is not stable at `temperature: 0` on the gateway).
