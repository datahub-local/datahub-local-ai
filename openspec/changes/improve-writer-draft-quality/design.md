# Design

## Context

The article lane is: pick row → draft (one turn, structure chosen inside it) → improvement
pass (aspects + edit-in-place) → Slack review → assets → publish. The post lane is: judge
(hook, angle, evidence) → queue → draft from row values → gate → review → visual → publish.
The judge's `angle` and `evidence` are parsed in `parse_judge` and never written anywhere;
the post writer and both visual briefs read the post text (or draft text) alone. The retry
forms are Retry/Cancel + free text in both lanes. The writer pod's every turn runs on
`opencode-go/deepseek-v4.1-flash` via `sympozium_pi_writer.model.name`.

Owner decisions, taken before this change: the outline choice is a **separate Slack
approval before drafting** (not attached to the draft review), and the model upgrade is
**blanket `opencode-go/glm-5.3`** (revised from `deepseek-v4-pro`; not per-turn).
## Decisions

### D1 — The outline is an adapter turn, blind to the network

`task: "outline"`, article lane only, rendered from `article_outline.md` in the writer
image, run `--no-tools` in the row's session. It sees exactly what the drafting prompt
sees at planning level: topic, description, source link, the row's `CONTENT` seed,
audience, extra rules, and `article_structures.md`. It does not spend Firecrawl lookups —
coverage and order are decidable from the seed; sourcing is the draft turn's job. It
answers one `<outline>` block with two or three candidate indexes, each a shape id, a
one-line outcome, and an ordered list of section names with a one-line job per section.
The server parses it the way it parses aspect findings and returns it as data; the graph
never reads the raw model text. An index a source cannot support is the draft turn's
problem to degrade (prose, not invented blocks) — the outline is guidance, not a contract.

### D2 — The outline choice is a blocking Slack form before the draft

Entry point: after the row is claimed, build the outline request, call the creator
sub-workflow (`TASK=outline`), parse, and post a `sendAndWait` form naming the subject
and listing each option's outcome line and section names. The form offers one dropdown
(option 1 / 2 / 3) and one textarea ("changes to the chosen outline"). The answer is
written to `article_queue.OUTLINE` (column added by hand before first run, like
`SOURCES`) and passed as `{{ OUTLINE }}` to the drafting turn; a non-empty textarea is
appended to the outline as the owner's edit. `article_task.md` and `article_improver.md`
state the rule once: write the article this outline describes, sections in this order,
each doing the job it names; feedback outranks it as today.

The wait joins the existing stale-claim regime rather than growing a new one: the row is
`IN_PROGRESS` on the outline form exactly as it is on the draft review, `pick_candidate`
re-claims it after the four-hour window, and the 7-day ceiling reads `UPDATE_DATE`, which
the outline phase writes.

An outline turn that fails or parses empty retries once, then the row goes `ERROR`
through `build_failure` — the same path a failed draft takes, and the notification says
the outline failed. Degrading to a blind draft would spend the run the owner chose to
gate.

### D3 — The gate never counts sections against the outline

`article_review.md` is unchanged by this work. The 2026-10-30 counted-sections registry
was reverted the same day (run 15259): the counts were not the binding constraint and the
gate enforcing them burned the bound while the draft stayed incoherent. The outline's
enforcement is the writer reading it and the human who approved it.

### D4 — Release hooks must state the change

`hook_types.json` `opening` for `RELEASE` becomes "open by naming the headline change —
what is new, spelled exactly as the article states it — then the implication to watch",
and for `NEWS_REACTION` "open with your immediate take, naming what was announced in the
same breath". The hook opening is injected into the post drafter's directives and judged
by `linkedin_post_review.md` through the existing directive check, so both halves move
with the one registry edit. The first version also carved the release's headline change
into the judge's angle rule; the angle field is now removed entirely (D8), so the registry
opening is the whole fix. Both files are fetched from `main`, so the change is live on
push; no graph apply.

### D5 — The judge selects and categorizes; the writer writes

Corrected twice in review. The live admission already wrote the judge's **evidence into
`RATIONALE`**; the angle it wrote into `EXTRA_PROMPT` — first duplicated into new
columns, then reverted — is now **removed outright** (owner decision): a ≤30-word
direction written by a cheaper model was steering a smarter one that is not allowed to
overrule it, and the Spark 4.3 post is that failure. The judge's job is categorization
(hook, visual form, scenes) and selection (postability, blocked, evidence); the position
the post argues is the writer's own, taken from the article text it already reads.
`EXTRA_PROMPT` returns to human-only free direction. What survives of the passthrough is
the one consumer that never saw the values:

- **Animated visual**: the studio call's `CONTENT` is prefixed with "The article's
  concrete detail: <`RATIONALE`>" when the row carries one. No studio contract change.
- **Still fallback**: `linkedin_image_prompt.md` carries an `{{ EVIDENCE }}` line beside
  `{{ POST_CONTENT }}`, filled from `RATIONALE` by the image-creator's template vars
  (the placeholder name is internal; the sheet column is unchanged).

Evidence is bounded (≤20 words), so the passthrough adds no payload risk. Blank cells
degrade to today's behaviour. The backfill pass writes neither, so a row repaired by it
keeps a blank cell — the same degrade.

### D6 — The retry menu is the form, the feedback path is unchanged

Both retry forms (`notification_retry_or_cancel`, the post text form) gain a `Directive`
dropdown: `Structure or order wrong`, `Wrong focus`, `Change tone`, `Make concise`,
`Explain more` (plus `Other`, the default). The FEEDBACK expression prepends the chosen
value in brackets to the textarea content. Nothing else moves: feedback already outranks
every rule in both lanes, so a named directive is just feedback with a stable wording.
The improver's contract already allows restructuring on a feedback round. `Wrong focus`
within the draft's frozen facts means re-weighting and cutting, not new research — that
is the existing edit contract and the menu does not promise more.

### D7 — Blanket model upgrade, one values change

`sympozium_pi_writer.model.name` → `opencode-go/glm-5.3` in
`agents/sympozium/values/default.yaml.gotmpl`; rollout is `helmfile apply` in
`agents/sympozium/`. The session server reads `MODEL_NAME` once per pod, so every turn
moves together. The LiteLLM gateway must route the model and (for the cost panel) carry
its `pricing.extraEntries` — both live in `datahub-local-core`; availability is verified
on the first run after the rollout, not assumed. `glm-5.3` is the strongest writing model
on the provider (~9× the flash tier's token price, $1.4/M in, $4.4/M out), and the
allowance, not the token price, decides it: the owner's account figures are **$200/month
of included usage on `glm-5.3`, against ~$100 on the deepseek family and $60 on
`glm-5.3-flash`** — so the writer's heavier pro-tier turns draw on the largest budget and
the fallback flash pair keeps the smallest. `[UNVERIFIED]` — account allowances are read
from the opencode-go dashboard, not this repository. Two limits ride along: the 2026-08-22
event in `agents/sympozium/MEMORY.md` measured `glm-5.3-flash` and `deepseek-v4.1-flash`
sharing one **5-hour** opencode-go budget, so whether `glm-5.3` sits inside that same
short window is a thing the first live run watches for (a 429 names it), not a thing this
design assumes either way. One tuning risk to watch on the first live run: the writer's
thinking level stays `minimal`, and the prompt discipline (word counting via
`check-article`) is model-agnostic, but the first draft on the new model is the real
test, not an assumption.

### D8 — The curator selects; the writer classifies and writes

Two owner decisions in one direction. The judge's `MODEL` moves to `opencode-go/glm-5.3`
(`set_workflow_vars`, both copies): selection is now its whole job — `postability`,
`blocked`, `evidence` — and the gate that decides what enters the queue at all deserves
the tier that writes. Its calls are small (≤12k characters in, a short JSON verdict out,
one per finalist, bounded per run), so the cost is cents. `MODEL_FALLBACK` stays
`glm-5.3-flash`; a fallback inside the same provider's quota is the known caveat.

The judge no longer categorizes. The `angle` field is removed outright — a ≤30-word
direction written by one model was steering a smarter one that could not overrule it (the
Spark 4.3 failure) — and the `hook` and `visual` fields move to the writer's draft turn,
which is when classification quality matters and which the stronger model performs
anyway. `build_post_request` already fetches the one registry; when the row's `HOOK` is
blank the brief carries the eligibility list (`when` + `opening` per hook) and the
writer answers `<hook>ID</hook>` beside the post, choosing exactly one hook whose `when`
the article satisfies. The graph validates the id against the registry in code, writes
`HOOK` plus the hook's registry visual defaults (`VISUAL_FORM`, `SCENES`) to the row at
parse, and the visual branch and still fallback read the row exactly as before —
classify-once holds, later. A row whose `HOOK` is already set (a human edit, a
pre-change row) keeps today's resolve path and the writer is told the assigned shape; a
retry continues the session, whose stored directives carry the chosen hook, so a
re-draft does not re-choose. The curator's backfill re-judge pass retires: hook-less
queued rows are no longer a defect to repair, they are the normal pre-draft state.

### D9 — Push order

The writer image holds the article prompts: build and pin the digest first, then apply
both article graphs in one `--changes` batch. The registry and judge edits are live on
push. **The image prompt is not**: `prompts/linkedin_image_prompt.md` now carries
`{{ EVIDENCE }}`, and `DownloadTemplate`'s `check_template_vars_present`
stops the run (`stop_and_error`) on any placeholder the caller's `template_vars` lacks —
measured against the committed export, which passes no such key. So the
`linked_in_image_creator` graph apply that adds both keys to the fetch **must land before
or with** the push of that prompt file; a push-first ordering breaks every still-fallback
image run. The post-lane graph edits are otherwise independent of the image and can apply
any time after their export edit. Live applies only after the owner sees the diff — the
standing rule.

## Risks

- **One more human round-trip per article.** Accepted by the owner. The form is the only
  new blocking gate, and the stale-claim window already bounds an unanswered one.
- **Outline options that promise what sources cannot support.** The draft turn degrades
  (prose, no invented blocks — the ledger enforces this already); the review message
  could name the outline so the owner can see the divergence. Tolerable: the outline
  names coverage, and the writer says an unknown as a fact about the software.
- **The outline turn costs one model call per article** on the pro tier. Bounded, and
  small against a draft that is rejected for structure.
- **A third retry-form field** could sit unanswered; the dropdown defaults to `Other`
  and the empty case behaves exactly as today.
- **New sheet columns are hand-added.** Precedent (`SOURCES`, `AUDIENCE`) says the lane
  reads them when present; a missing column is a write the run fails on, so the columns
  land before the first live run of the touched nodes.
- **Model rollout.** The pod's whole fleet of turns depends on the gateway routing the
  new id; a gateway miss fails loudly (the drafting turn errors) and rolls back by
  reverting one value. The allowance figures are the owner's dashboard readings
  (`[UNVERIFIED]` here), and the shared 5-hour window measured for the flash pair may
  apply to `glm-5.3` too — the first live run is the check for both.

## Open questions

- Should the outline options appear in the draft review message too (informational, so a
  retry can name another option)? Leaning yes — one line each, no new interaction.
- Whether `EVIDENCE` should also ride the `LinkedIn Image Creator`'s retry round (the
  feedback form there names art direction). Leaning no; scope stays the draft forms.

## Definition of done

- An article row drafts only after its outline is approved in Slack; the approved index
  is on the row and the draft's sections follow it, order included.
- An unanswerable outline fails the row `ERROR` with the reason, not a blind draft.
- A `RELEASE`-hooked post names the headline change in its opening lines; the gate reads
  the new opening through the existing directive check.
- The retry form's directive value reaches the writer inside `FEEDBACK`, verbatim.
- A queued post's angle and evidence appear in `content_queue`, and the animated branch's
  brief names the article's concrete detail.
- The writer pod answers on `glm-5.3` for a full draft run.
- `openspec validate --all` passes; the adapter tests (`node --test`) cover the outline
  parse; the workflow invariants tests pass over both edited exports.
