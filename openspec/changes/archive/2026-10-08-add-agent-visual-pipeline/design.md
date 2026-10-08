# Design

## Context

Today a visual is produced in two stages: a model writes a typed **content spec**
(`title`, `blocks`, `accent`, `motion`), and deterministic code turns that spec into
markup from a template or a layout module. The model never authors the visual; it fills
a form. That is what makes the pipeline safe and reproducible, and also what makes it
unable to draw anything the form does not already describe.

The agent path (`agent-authored-compositions`) already exists: a `pi-render` session
takes a brief, authors a HyperFrames composition and renders it. It is the piece to
grow.

## Decisions

- **D1 — One agent, two jobs, one turn.** The composer first plans a storyboard and then
  authors the composition, in the same `POST /v1/chat/completions` turn. A separate
  director agent would add a model hop and a second contract for little gain; the
  planning is a paragraph in the agent's authoring guide and a field in its report.
- **D2 — The storyboard is the plan, not an artifact the workflow parses.** Unlike the
  old content spec, nothing downstream reads it: it is the agent's own reasoning made
  visible in the run record, so a bad visual can be diagnosed. The workflow does not
  validate or transform it.
- **D3 — `FORCE` is an enum, not free text.** `auto | diagram | story | data | poster |
  image`. `auto` lets the agent choose; anything else pins the form. A free string would
  be unreviewable and hard to test.
- **D4 — `STYLE` is a brand scheme.** `dark | light`, from `datasets/brand.json`, the
  tokens extracted from `datahub-local.alvsanand.com`. A caller cannot introduce a
  palette the brand does not define, which is the rule the brand test enforces.
- **D5 — Three types.** `image` (Gemini, png), `animation` (composer, mp4),
  `animation_linkedin` (composer, gif, inside the platform cap). The old type ids go.
- **D6 — The deterministic path is removed, not kept as a fallback.** Two renderers is
  the complexity being retired; a plain image stays on Gemini because it is a different
  medium, not a fallback for an animation.
- **D7 — A failed composer falls back to the image**, exactly as the animated branch
  does today: the post still publishes, with a still image and a Slack notice naming the
  reason. Agent authoring is slower and non-deterministic, so the failure path matters
  more, not less.

## Risks

- **Non-determinism**: the same content can produce a different visual. Accepted; the
  old "frozen spec renders identically" guarantee goes away for `animation`.
- **Cost and latency**: an authoring turn plus a render is minutes. The type's
  `runTimeout` and the session's resources bound it; the fallback (D7) covers a timeout.
- **Quality drift**: the agent's output is only as good as its guide. The guide is a
  prompt file, so it is reviewable and changeable without a deploy.

## Open Questions

- Whether `FORCE` should also be settable per row (a content-queue column) as well as
  per request. Deferred; the trigger carries it first.

## Definition of done

- A request for `animation` with `FORCE=diagram` and `STYLE=light` returns a rendered
  composition whose form is a diagram in the light scheme.
- A request for `image` still returns a Gemini png, unchanged.
- The render service, the typed spec and the layout modules are gone from the repo.
