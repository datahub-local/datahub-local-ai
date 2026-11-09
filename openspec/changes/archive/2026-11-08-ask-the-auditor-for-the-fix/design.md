# Design

## Gate findings

- `prompts/article_audit.md` told the auditor to search `PI_WRITER_SESSION_FILE`; only
  `PI_WRITER_SESSION_ID` and `PI_WRITER_SESSION_DIR` were set. The transcript was unreachable.
- The audit ran with tools but with `proxyEnv(null)`, so no fetch had a route; its "six lookups"
  could not happen.
- `deriveLedger` discarded the block text and returned only its first line, so the caller's
  `UNQUOTED` feedback named `apiVersion: sympozium.ai/v1alpha1` twice with nothing to act on.
- The improver was forbidden to fence and could not fetch, so the only permitted response to "add
  three examples" was deleting the section.

## D1 — The gate list is an input, not the auditor's discovery

The adapter calls `writeDerivedLedger` before the audit and passes `unquotedBlocks` and the
session's page URLs into the prompt. The auditor's job becomes conversion: each block gets a
concrete fix. This is the same division as the merge node — code counts, the model judges — with
the count handed over instead of hidden.

## D2 — The adapter sets the verdict floor

`pass = verdict.pass && unquoted.length === 0`. The audit remains advisory on everything else, but
a draft the gate rejects can never come back as a pass, which is the state that misled the retry.

## D3 — Evidence has to be reachable

The transcript path is resolved with the same function the ledger uses (`transcriptFile`) and
passed as `PI_WRITER_SESSION_FILE`; the audit and improve turns get `articleHosts` + `proxyEnv`
like the draft. A tool-enabled turn without a route is a prompt that reads as research and behaves
as a guess.

## D4 — The edit turn researches only to quote

`improve` keeps its contract (apply the named findings, leave the rest alone) and gains the
allowlist and a four-lookup budget for one purpose: making a fenced block byte-for-byte. Its
remaining "no new facts" rule is unchanged, and `check-article` gives it the same self-check the
draft has.

## Risks

- The improver can now read pages it is not asked about and drift. Bounded by the finding text,
  the four-lookup cap and the derived ledger, which still rejects any block no page carries.
- A rejected block the auditor cannot source is now removed or de-fenced, which can thin a
  section. That is the existing trade: bronze-style invention is worse than a shorter article.
- [UNVERIFIED] live behaviour of the audit's fix quality at `minimal` thinking until the next run.

## Definition of done

- The audit's prompt names each unquoted block and the pages read; its pass is false whenever one
  remains.
- `PI_WRITER_SESSION_FILE` is set for the audit; the proxy is on for audit and improve.
- An edit that must quote a page can fetch it, and runs `check-article`.
- `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` and `openspec validate --all` pass.
