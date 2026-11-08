# Design

## Gate findings

- Pi's transcript row for a tool result carries `toolName`, `toolCallId` and the text the model
  received, and the assistant row carries the arguments (including `url`). Both are needed:
  the URL is only in the call, the text only in the result.
- The result text is what the model saw, including Pi's own `Warning: truncated output` prefix.
  Matching against the seen text is deliberate: a fence that only exists beyond the truncation
  point was never read, so it must not verify.
- Firecrawl's result is sometimes markdown and sometimes `{"markdown": "..."}`; the wrapper has
  to be unwrapped before matching, exactly as the removed scrape reader did.
- The gate reports three different failures and they stay distinct: no entry is `UNQUOTED`, an
  entry with `found: false` is `SOURCE_NOT_FOUND`, a `validation_error` is `VALIDATION_FAILED`.
  Derivation emits only the first two.

## D1 — Derive, do not re-read

The old path asked the model to declare the provenance and then re-fetched each declared URL to
check the declaration. Both halves are replaced by one lookup over the scrape results the pod
already brokered: the request proves the page answered, the transcript proves what the model
read, and the match proves the fence is on it.

Rejected: keeping the re-read as a second opinion. It fails on the pod's own egress policy
unless it goes through Firecrawl, it drops correct entries when a page answers slowly, and it
never caught the failure this change exists for.

## D2 — One entry per matching block, first page wins

A block can appear on several scraped pages. The first match in transcript order is recorded,
which is the page the model most likely read it from. Rejected: recording every page (the gate
reads one entry per block, and a duplicate invites two verdicts).

## D3 — The model stops writing the file

`sources.json` is server output now. Telling the model to write it as well would be a second
copy, and the reason this change exists is that the copy drifted. The prompt keeps the part the
model must do: quote verbatim from a page it scraped.

## Risks

- A fence that appears only in a page fetched with `bash curl` will not verify. The sandbox map
  and the research section name Firecrawl as the only read path, so this is the intended state;
  a future curl path means extending `transcriptPages`.
- Matching uses whitespace-collapsed tokens, the same rule the gate applies, so a block with a
  changed word still fails. That is the contract, not a regression.
- [UNVERIFIED] live: a real run on a rebuilt image. The unit tests build a transcript fixture
  with the row shapes observed on the pod.

## Definition of done

- A draft turn writes `sources.json` derived from its own transcript, with no model ledger.
- The fetch family is gone, and every remaining test passes.
- `openspec validate --all` passes.
