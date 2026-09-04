# homelab-responder

One persona, and the only channel-bound one in this repository. It is split into
its own ensemble because ensemble-level settings apply to every persona inside,
and the trust boundary here is inbound: an @-mention from Slack starts a run, and
such a run gets **no `toolPolicy`** at all. Its real bounds are therefore
`mcpServers[].toolsAllow`, which filters at the server and survives that path,
and mounting no skill sidecar, which leaves `execute_command` nothing to execute.

That is also why the Slack sender allowlist is **unset** — anyone in the
workspace may ask it something (2026-09-04). `allowedSenders` never was the
boundary, since the inbound path discards `toolPolicy`; the boundary is the
read-only `toolsAllow` list in `agents/homelab-oracle.yaml`. Narrow there, not
in `values/`. Full reasoning, and what a workspace member can now spend, in
`../../MEMORY.md`.

It carries no `lifecycle.postRun` hook, deliberately. The hook posts to one fixed
channel, which is how two questions asked in two different channels were both
answered into a third. Without it the reply flows back through the channel
sidecar to the thread that asked.

It is the only bound persona, which also means it is the only one whose sidecar
exists — and every channel sidecar delivers every instance's outbound message on
an unfiltered fleet-wide subject, so a second binding would mean two copies of
everything.

Why the knobs are set the way they are: `../../MEMORY.md`.
