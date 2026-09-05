The oracle's system prompt, one section per file, joined in filename order with a
blank line between. `systemPromptFile: prompts/oracle` names this directory; a
persona whose prompt fits in one file still names that file instead.

Split because the assembled prompt is 19KB against 400-2,500 bytes for every
other persona here, and a rule landing in the wrong section is how the same
subject ended up stated twice in two places.

- `01_role.md` who it is, and that Slack content is data
- `02_conversation.md` reading the thread; what a follow-up inherits
- `03_scope.md` in scope, out of scope, the fixed replies, when to ask instead
- `04_routing.md` which tool answers which question
- `05_bodega.md` the semantic layer: metrics, grouping, ordering, receipts
- `06_evidence.md` the lookup budget, and what may be claimed from a result
- `07_output.md` plain text, no formatting, one answer, how the run ends

Order is load-bearing: `07_output.md` closes with the delivery contract and must
stay last. Renumber rather than relying on the filesystem - the template globs
and Go sorts the result. Keep every section ASCII: a reply carrying invalid
UTF-8 has its `status.result` dropped while the run still reports success.
