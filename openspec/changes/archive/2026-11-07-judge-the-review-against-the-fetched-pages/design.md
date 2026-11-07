# Design

## D1 — The session transcript is the fetched corpus

The review turn already resumes the drafting session: same `--session-id`, same session directory,
one turn after the other. The pages the writer read with `curl` are in the earlier turns of that
transcript, and the verified ledger names their URLs. The review prompt had told the model that
the `<source>` block was "what the writer fetched during the run", while the block carried the
entry's seed page. That named the wrong artifact and invited the rejection.

The fix points the reviewer at the transcript and the ledger, and scopes the fact check to
"everything the writer read", not "the seed page". No new transport or storage is needed.

Rejected: re-fetching the ledger URLs inside the review turn. The adapter already fetched them to
verify the ledger; fetching them again adds latency and a second chance for the page to change,
and it would still miss a page the writer read without fencing a block.

Rejected: storing the full pages in `sources.json`. The artifact is small and the workflow copies
it to a sheet cell; full page text would make one cell carry the whole corpus.

## D2 — The seed page stays the entry's source

The entry's `CONTENT` is still the seed page and still the first thing the reviewer reads. The
change does not let a draft invent facts: a fact absent from the entry's inputs, the seed page and
every fetched page is still a failure, and a citation of a page the writer did not fetch is still
a failure.

## D3 — The prompt names the evidence

The prompt says the fetched pages are "in this session's earlier turns" and "the ledger names
them". Both are true and both are available to the model, so the instruction is checkable rather
than a hope. The fact rule repeats the same scope in one sentence, because the reviewer reads the
checks as the contract.
