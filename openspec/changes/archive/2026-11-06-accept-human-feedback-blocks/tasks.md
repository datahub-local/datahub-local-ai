# Tasks

## 1. Code

- [x] 1.1 `check_improved_draft`: accept a fenced block no ledger entry carries when the round has
      human feedback, count it in `UNVERIFIED`, set `FIDELITY: "feedback"`. Keep failing a ledgered
      block that is `found: false`, failed validation or drifted.
- [x] 1.2 `check_improved_draft`: set `UNCHANGED` when the returned body and title equal the ones
      the round was given.
- [x] 1.3 `select_final_draft`: report `UNCHANGED`, keep the base draft, carry `UNVERIFIED` into
      `IMPROVEMENT_NOTE`.
- [x] 1.4 `notify_article_review`: name the unverified count in the Slack message.
- [x] 1.5 Both export copies (`nodes` and `activeVersion.nodes`) patched identically.

## 2. Prompt

- [x] 2.1 `article_improver.md`: a command or output the feedback names may be written even when
      the draft and the sources do not carry it, and is reported unverified.
- [x] 2.2 `article_improver.md`: a feedback round must change the draft.

## 3. Tests

- [x] 3.1 Feedback round accepts and counts an unverified block.
- [x] 3.2 First-draft edit still rejects it.
- [x] 3.3 Feedback round still rejects a ledgered block the page lost.
- [x] 3.4 Unchanged edit is reported as unchanged.
- [x] 3.5 Unchanged edit is not an improvement in `select_final_draft`.
- [x] 3.6 Unverified count reaches the converged draft and its note.
- [x] 3.7 Red-first: the four code tests failed against the unpatched workflow; suite green after.

## 4. Docs and spec

- [x] 4.1 `docs/agent/n8n.md`: the feedback-round exception beside the ledger rule.
- [x] 4.2 `docs/agent/n8n.md`: `UNCHANGED` and the unverified count beside the retry outcomes.
- [x] 4.3 Delta applied to `content-writer` and archived.

## 5. Deploy

- [ ] 5.1 Apply the graph to the live instance and read back both copies matching the export.
      [UNVERIFIED] until run.
- [ ] 5.2 After `main` carries the prompt, one live retry with the owner's feedback, and the stored
      draft differs from the one that was rejected. [UNVERIFIED] until run.
