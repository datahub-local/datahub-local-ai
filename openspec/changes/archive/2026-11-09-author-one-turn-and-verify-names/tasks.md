# Tasks

## 1. Verify by names

- [x] 1.1 `session-lib.mjs`: `isNameToken`, per-language `blockNames`, `verifyBlock`.
- [x] 1.2 `deriveLedger`: `mode: "quoted"` for a copy, `mode: "derived"` for a covered compose,
      and a reason naming the missing names for a rejection.
- [x] 1.3 `check-article` prints the reason with each `MISSING` line.

## 2. The gate reads the mode

- [x] 2.1 `parse_article`: a `derived` entry is accepted by its names, a `quoted` one keeps the
      excerpt comparison.
- [x] 2.2 `check_improved_draft` holds the same rule, so an on-demand edit is not judged by the
      old one.

## 3. One turn

- [x] 3.1 `article_content_writer`: `first_draft` replaces `select_final_draft`; the aspect and
      edit nodes and their connections are removed; the review message drops the improvement line.
- [x] 3.2 `article_creator`: `MAX_TRIES` 3 → 2.
- [x] 3.3 The session id carries the round and the attempt; `isIteration` follows the directory.

## 4. Prompts

- [x] 4.1 `writing.md`: the two ways a block is verified, and no emptying a section to pass.
- [x] 4.2 `article_audit.md` and `article_improver.md` state the same rule.

## 5. Gates

- [x] 5.1 Tests for a covered compose, an invented name, a malformed block and the mode round-trip.
- [x] 5.2 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes.
- [x] 5.3 `openspec validate --all` passes.
