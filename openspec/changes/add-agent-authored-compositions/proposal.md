# Proposal

## Why

The render service answers one shape of demand: a *typed spec* in, a deterministic
video out. Its vocabulary is whatever its layouts and vendored blocks can express —
today a handful of arrangements of labelled figures. That is the right contract for
a scheduled workflow, and the wrong one for a bespoke brief: "show how a team of AI
agents collaborates to build a project" has no layout, and no catalog block either.

The capability that fits is already installed and working: HyperFrames ships
**agent skills** (`hyperframes skills` — 21 of them, including `hyperframes-core`
for the composition contract and `hyperframes-animation` for motion), and an agent
that reads them can author an arbitrary composition and render it with the same
toolchain the render service ships. This was proven on 2026-10-04: a one-sentence
brief produced a 9-second 1080×1350 animation the service could not have generated,
with HyperFrames' own `lint` catching two real defects that the agent then fixed.

Today that capability exists only as a hand-run experiment. This change makes it a
declared, reviewable path — and answers whether it can run in the cluster's
Sympozium agent fleet through the **Pi** harness, which the cluster already has
installed but no persona uses.

## What Changes

- **Declare agent-authored compositions as a supported capability**, distinct from
  the render service's typed spec: the agent writes the composition, HyperFrames is
  the engine, and the composition is a reviewable artifact rather than a request
  payload. The render service's API is unchanged and keeps rejecting caller markup;
  this path is not that API.
- **Make the authoring loop reproducible**: the skill set that teaches the agent the
  composition contract is a declared dependency, pinned, and the `lint` → fix →
  render gate is part of the procedure rather than a suggestion.
- **Keep compositions offline**: no CDN, a vendored GSAP, and the same image
  toolchain, so a render works with no network.
- **Record the cluster path.** The `Agent` CRD has a `runtimeRef` that replaces
  `agent-runner` with an administrator-approved `AgentRuntime` in harness mode, and
  the cluster already carries a ready `pi-session-v0-84-4` runtime. Whether a Pi
  persona can author and render a composition is a **gate to answer before any
  persona is declared**, not an assumption: the gate is a hand-applied `AgentRun`
  probed for file-write, command-execution and toolchain reachability.
- **Ship the proven sample** as a committed artifact with the procedure that
  produced it, so the path is demonstrated rather than described.

## Capabilities

### New Capabilities
- `agent-authored-compositions`: an agent authors a HyperFrames composition from a
  brief, gates it with HyperFrames' own validation, and renders it offline — with
  the composition committed as the artifact of record.

### Modified Capabilities
- None. The render service's contract is unaffected; this adds a second, separate
  path and must not weaken the first.

## Impact

- `agents/render-samples/` — the committed sample and its procedure (added).
- `agents/sympozium/` — a persona using `runtimeRef: pi-session-v0-84-4`, **only if
  the gate passes**; the Pi runtime's capability surface is unverified today.
- `agents/n8n/render/` — unchanged. It keeps its spec contract, its vendored blocks
  and its `lint`-free deterministic path. The two must not be conflated: the sample
  directory exists precisely because they are different products.
- The `migrate-render-layouts-to-catalog-blocks` change is **narrowed** by this
  discovery: the catalog can back only `comparison` and `stats`, so its goal of
  removing every hand-written layout is unreachable and it should be re-scoped to
  "add catalog data blocks alongside the layouts", or superseded.
- **A follow-up is now known to exist** and is deliberately not part of this change:
  the Sympozium **Pi and Hermes harness adapters disable tools and skills** (their
  own documented behaviour), so they cannot author a composition — but tool use is
  the *adapter image's* business, and the platform supplies everything a tool-using
  adapter needs (`/workspace`, a writable `$HOME` emptyDir, writable `/tmp`, UID
  1000, its own `ENTRYPOINT`). A purpose-built **hyperframes harness adapter** could
  run authoring in the fleet. It is real work — toolchain baked into the image,
  adapter-owned state, conformance, an `AgentRuntime` registration — and the
  capability is already proven without it, so it is recorded in
  `pi-harness-findings.md` rather than built here.
