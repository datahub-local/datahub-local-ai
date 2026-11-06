# Tasks

## 1. State the contract every shape inherits

- [x] 1.1 Rewrite the shape preamble in `article_structures.md` as one outcome, one path, names
  carried forward, one job per section, numbered steps as one sequence and a step that ends on what
  the reader sees. Verified by reading the rendered drafting brief in the adapter test
  (`a brief is rendered from the adapter's own prompt files`).
- [x] 1.2 Rewrite *Getting started* as a single numbered path: prerequisites complete before step 1,
  the trap as a paragraph where it bites, an unnumbered close. Verified by the same render.
- [x] 1.3 Add the step shape and the no-narration rule to `article_task.md`, and drop the research
  section's references to tools the pod does not have.

## 2. Make the gates reject the four observed defects

- [x] 2.1 Add one path, one job, numbering, no process narration and the close to
  `article_review.md`, so the drafting gate retries with the failure named.
- [x] 2.2 Add the same structure findings to `article_aspect_structure.md` and the keep-the-spine
  rule to `article_improver.md`.
- [x] 2.3 Add rhythm, specificity and the machine-written tells to `article_writer_system.md`.

## 3. Record it

- [x] 3.1 State the 15928 evidence and the contract in `docs/agent/n8n.md`.
- [x] 3.2 Write the `content-writer` delta and archive the change.

## 4. Verify

- [x] 4.1 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` — 31 passed.
- [x] 4.2 `uv run -- pytest agents/n8n/scripts/ -q` — see the pull request body.
- [x] 4.3 `openspec validate --all` — see the pull request body.
- [ ] 4.4 One live draft after the image and graph are deployed: `[UNVERIFIED]` until a run, and the
  stored draft for the entry must differ from `gh-80`'s round 1 and read as one path.
