# Proposal

## Why

Run 15928 (2026-11-06) delivered a walk-through the owner cancelled as incoherent. Four defects, all
visible in the stored draft:

- The ensemble built in step 4 is `example-team` with the persona `analyst`; step 5 pastes the
  project quickstart's `quickstart-demo` with `assistant`, so the run it applies cannot exist in the
  cluster the reader just built.
- A complete Helm install sits as `### 3.1` inside the step the CLI route has already completed, and
  introduces cert-manager after the prerequisites section closed.
- "Break it on purpose" is a second teaching section after the walk-through ended, about a policy and
  sandbox model the article never explained when it showed `policyRef`.
- The close narrates the writing: "I have not pasted a sample here — I did not run this against a
  live cluster".

The three aspect reviewers named the first three; the improvement pass fixed them and the code
re-check rejected the edited YAML and command, so the fallback presented the cancelled draft. The
drafting prompt had no rule against any of them: the shapes were a list of section duties, numbering
was unconstrained, and nothing required a later step to use the names the article created.

## What Changes

The prompt files named below live in `agents/adapters/pi-writer/prompts/` after the move recorded in
`move-the-article-prompt-to-the-writer`, which lands on the same branch.

- **`article_structures.md`** states the rules every shape inherits: one outcome, one path, names
  carried forward, one job per section, numbered steps as one sequence with an unnumbered close, and
  a step that ends on what the reader sees. *Getting started* becomes a single numbered path with the
  trap as a paragraph and the prerequisites complete before step 1.
- **`article_writer_system.md`** adds rhythm and specificity rules and the machine-written tells:
  no one-line restatement, no contrast against a claim nobody made, no staged opener, no straw-man
  defence, no forced trio, no bold decoration, no heading repeated under itself, no text about the
  text, no significance close. Paragraphs run two to four sentences and sentence length varies.
- **`article_task.md`** adds the step shape and forbids two pages' examples in one path and any
  narration of the writing.
- **`article_review.md`** rejects the four defects, so the drafting gate retries with the failure
  named instead of handing them to the improvement pass.
- **`article_aspect_structure.md`** and **`article_improver.md`** carry the same rules into the
  improvement pass.

## Capabilities

`content-writer`.

## Out of scope

- The improvement pass's fenced blocks are still frozen by the ledger: when a structural fix needs an
  edited command, the edit is rejected and the fallback draft is delivered. That is the observed
  second half of run 15928 and needs its own decision; the drafting prompt now aims to remove the
  need, but the pass cannot be trusted to fix a command.
- No code gate on heading numbering: the cancelled draft numbers 1 to 6 with an unnumbered close,
  which such a gate would pass, so it would not prove anything about this issue.
