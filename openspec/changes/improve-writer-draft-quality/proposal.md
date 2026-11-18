# Proposal

## Why

Three defect classes, all observed by the owner on published output:

1. **Article structure does not follow the article's point.** The Sympozium walk-through
   (run 15928) shipped two name systems, a Helm install nested inside the step the CLI
   had completed, and a teaching section after the walk-through had closed. The shape
   choice is one implicit decision inside the single drafting turn; the structure aspect
   reviews it only after the whole article is paid for, and the improvement pass is
   edit-in-place — the owner still cancelled. The blog lane has no intake judge at all:
   a board issue becomes a row and the writer decides coverage and order alone.
2. **Release posts skip the news.** A Spark 4.3 post opened on an advanced tension and
   never stated what changed. Written causes: the judge's angle rule bans handing back
   "a fact the article already states" — for a release, the headline change is that fact
   — and the `RELEASE`/`NEWS_REACTION` hook openings demand a take with no requirement to
   name the change itself.
3. **Retry feedback is free text only.** The Slack retry forms offer Retry/Cancel plus a
   textarea; the common asks (fix the order, wrong focus, tone, concision, depth) are
   retyped every time.

Two adjacent gaps ride along: the judge's `angle` and `evidence` verdicts are parsed and
dropped — `content_queue` has no columns for them, so neither the post drafter nor the
visual brief ever sees the one concrete detail that justified admission; and the writer
pod runs on `deepseek-v4.1-flash`, the tier the lane's own history calls the least
reliable pair in the fleet.

## What Changes

- **A pre-draft outline for articles.** A new `task: "outline"` turn in the pi-writer
  adapter proposes two or three candidate indexes (shape, ordered section names, one-line
  job each). The entry point puts them in a Slack approval form before drafting; the
  chosen index is stored on the row and given to the draft and improve turns as the plan
  to write to. The drafting gate does not count sections against it.
- **The news opening is required, not implied.** `RELEASE` and `NEWS_REACTION` hook
  openings state the headline change in the first lines, then the take.
- **A directive menu on the retry forms.** Both draft/post retry forms gain a dropdown
  (structure or order wrong / wrong focus / change tone / make concise / explain more)
  whose value is prepended to the free-text feedback.
- **The judge stops writing direction — and classification moves to the writer.** The
  `angle` field is removed from the classification outright, and the `hook`/`visual`
  choice moves into the drafting turn: a row with a blank `HOOK` carries the registry's
  eligibility list on its brief and the writer answers `<hook>ID</hook>`, whose parse
  writes `HOOK` and the hook's visual defaults to the row. The curator becomes a pure
  selection gate (postability, blocked, evidence, on `glm-5.3`), the classify-once
  invariant holds at draft time, and the backfill re-judge pass retires. The one consumer
  that never saw the judge's values — the visual path — receives the article's evidence
  (`RATIONALE`) beside the post text.
- **The writer pod moves to `opencode-go/glm-5.3`.** One values change; the outline
  turn, the draft and the improvement pass run on the stronger tier.

## Capabilities

### Modified Capabilities

- `content-writer`: an approved outline precedes the article draft; the draft and the
  improvement turn write to it; the retry form offers named directives.
- `post-hook-taxonomy`: `RELEASE` and `NEWS_REACTION` openings require the change itself,
  and the judge's angle may be the change.
- `linkedin-post-publishing`: the visual briefs carry the row's evidence (`RATIONALE`)
  and angle (`EXTRA_PROMPT`); the post retry form offers named directives.

## Impact

- `agents/adapters/pi-writer/` — the outline prompt and `task: "outline"` handling; the
  `{{ OUTLINE }}` sections; the outline's precedence over a structure the Description
  itself sketches. Image rebuilt and digest pinned (graph edits wait for it).
- `agents/n8n/workflows/article_content_writer.workflow.json` and
  `article_creator.workflow.json` — outline phase before drafting, outline Slack form,
  `OUTLINE` passthrough, retry-form dropdown.
- `agents/n8n/workflows/linked_in_post_sharing.workflow.json` — retry-form dropdown;
  the visual calls read the row's `RATIONALE` (evidence) and `EXTRA_PROMPT` (angle).
- `agents/n8n/workflows/content_feed_curator.workflow.json` — no change: the live
  admission already writes the angle to `EXTRA_PROMPT` and the evidence to `RATIONALE`.
- `agents/n8n/datasets/hook_types.json`, `agents/n8n/prompts/curator_judge.md`,
  `agents/n8n/prompts/linkedin_image_prompt.md` — opening text, angle carve-out,
  evidence block. Live on push (fetched from `main`).
- `agents/sympozium/values/default.yaml.gotmpl` — `sympozium_pi_writer.model.name`.
- Hand-added sheet columns before first run: `article_queue.OUTLINE` only. The
  `content_queue.ANGLE`/`EVIDENCE` columns added first were reverted in review — the
  judge's angle and evidence already live in `EXTRA_PROMPT`/`RATIONALE`, and the curator
  appends exactly the 22 columns the sheet keeps.
- Cross-repo: `datahub-local-core` LiteLLM routing for `glm-5.3` and its
  `pricing.extraEntries` — the gateway's model availability is a rollout dependency, not
  this change's code. `[UNVERIFIED]`

## Non-goals

- Gate-enforced section counts. The counted-sections registry was built and reverted the
  same day (run 15259); the outline binds the writer and the human, never the gate.
- An outline step for posts. A post is one paragraph-plan; the hook opening already
  decides its shape.
- A re-draft path from the article retry menu. The Slack retry keeps re-entering the
  improvement pass; a fundamentally wrong draft stays a Cancel, not a menu option.
- Changing the image retry form. Its feedback is visual art direction; the draft
  directives do not apply.
- Per-turn model routing (strong model on draft, flash on review). Blanket upgrade only;
  the adapter keeps one `MODEL_NAME`.
