# Design

## D1 — The session transcript is the fetched corpus

The review turn already resumes the drafting session: same `--session-id`, same session directory,
one turn after the other. The pages the writer read with `curl` are in the earlier turns of that
transcript. The verified ledger names the pages a fenced block was read on; it is not the whole
record, because a page read for prose alone has no block to name. The review prompt had told the
model that the `<source>` block was "what the writer fetched during the run", while the block
carried the entry's seed page. That named the wrong artifact and invited the rejection.

The fix points the reviewer at the transcript and scopes the fact check to "everything the writer
read", not "the seed page". No new transport or storage is needed.

Rejected: re-fetching the ledger URLs inside the review turn. The adapter already fetched the
ledgered pages to verify their blocks, but that set is not every page the writer read, and
fetching them again adds latency and a second chance for the page to change.

Rejected: storing the full pages in `sources.json`. The artifact is small and the workflow copies
it to a sheet cell; full page text would make one cell carry the whole corpus.

## D2 — The seed page stays the entry's source

The entry's `CONTENT` is still the seed page and still the first thing the reviewer reads. The
change does not let a draft invent facts: a fact absent from the entry's inputs, the seed page and
every fetched page is still a failure, and a citation of a page the writer did not fetch is still
a failure.

## D3 — The prompt names the evidence

The prompt says the fetched pages are "in this session's earlier turns". That is where the tool
output lives, and it is the only complete record, so the instruction is checkable rather than a
hope. The fact rule repeats the same scope in one sentence, because the reviewer reads the checks
as the contract.

## D4 — The source link is not a fetched page

The seed page arrives in the brief, never through `curl`, and the draft must end with
`Source: {{ URL }}`. The citation rule names that exception explicitly: a page the writer did not
fetch is a failure, except the entry's own source link. Without it the gate would reject every
draft for its mandatory source line, which is the same literal-reading trap the marker-form and
H1 rules already recorded.
