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
  openings state the headline change in the first lines, then the take; the judge's angle
  rule gains the release carve-out so the angle may name what is new.
- **A directive menu on the retry forms.** Both draft/post retry forms gain a dropdown
  (structure or order wrong / wrong focus / change tone / make concise / explain more)
  whose value is prepended to the free-text feedback.
- **The judge's angle and evidence reach the consumers.** `content_queue` gains `ANGLE`
  and `EVIDENCE` columns; the post writer brief receives the angle, and the visual briefs
  (animated branch and the still image director) carry the evidence beside the post text.
- **The writer pod moves to `opencode-go/glm-5.3`.** One values change; the outline
  turn, the draft and the improvement pass run on the stronger tier.

## Capabilities

### Modified Capabilities

- `content-writer`: an approved outline precedes the article draft; the draft and the
  improvement turn write to it; the retry form offers named directives.
- `post-hook-taxonomy`: `RELEASE` and `NEWS_REACTION` openings require the change itself,
  and the judge's angle may be the change.
- `linkedin-post-publishing`: the queue row carries `ANGLE` and `EVIDENCE`; the angle
  reaches the post drafter, the evidence reaches both visual briefs; the post retry form
  offers named directives.

## Impact

- `agents/adapters/pi-writer/` — new `article_outline.md` prompt and `task: "outline"`
  handling; `article_task.md`/`article_improver.md` gain `{{ OUTLINE }}`; the post lane's
  brief gains the angle. Image rebuilt and digest pinned (graph edits wait for it).
- `agents/n8n/workflows/article_content_writer.workflow.json` and
  `article_creator.workflow.json` — outline phase before drafting, outline Slack form,
  `OUTLINE` passthrough, retry-form dropdown.
- `agents/n8n/workflows/linked_in_post_sharing.workflow.json` — retry-form dropdown,
  angle/evidence passthrough into the visual calls.
- `agents/n8n/workflows/content_feed_curator.workflow.json` — `admit_to_backlog` writes
  `ANGLE`/`EVIDENCE`.
- `agents/n8n/datasets/hook_types.json`, `agents/n8n/prompts/curator_judge.md`,
  `agents/n8n/prompts/linkedin_image_prompt.md` — opening text, angle carve-out,
  evidence block. Live on push (fetched from `main`).
- `agents/sympozium/values/default.yaml.gotmpl` — `sympozium_pi_writer.model.name`.
- Hand-added sheet columns before first run: `article_queue.OUTLINE`,
  `content_queue.ANGLE`, `content_queue.EVIDENCE`.
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
