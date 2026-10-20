# Proposal

## Why

Two gaps in the article lane, both visible on the first published articles (2026-10-18/19).

1. **Nothing improves a draft.** `Article Creator`'s internal loop is a *correctness* gate —
   budget, markers, facts, rules — and it accepts the first draft that breaks none of them. The
   plot, the section order, the pacing, are whatever the drafting pass produced first. The only
   quality pass is the human approval, and its Retry regenerates through the whole drafting loop:
   measured on run 14178, two human rounds each wrote a fresh article against feedback that named
   one section. No agent reviews the draft by aspect before the human sees it, so the human is the
   only thing between a first draft and the blog.
2. **Every article is written for one reader.** `article_writer_system.md` hardcodes it: "smart,
   busy and new to the subject". A row cannot ask for a practitioner-level article, so a
   Kubernetes-native CRD walkthrough and a getting-started guide get the same orientation, and
   the internal gate then enforces term explanations the intended audience never needed —
   execution 14055 burned four drafts and twenty minutes on exactly that mismatch before the
   gate's scope was narrowed.

## What Changes

- **An improvement pass between the returned draft and the human review.** After `Article Creator`
  returns a gate-passed draft, and before the draft is stored and uploaded for review: one
  **aspect reviewer** per aspect — a registry, not a graph enum — reviews the draft and returns
  advisory findings; an **improvement agent** edits the draft applying the findings and any human
  feedback; a **code re-check** verifies the budget and the asset markers survived the edit,
  retrying the improvement once with the objective problem and otherwise falling back to the
  gate-passed draft, recorded.
- **The Slack Retry re-enters the improvement pass.** The retry edge rewires from
  `execute_article_creator` to the improvement context, carrying the reviewer feedback and the
  draft the human read — a targeted edit, not a regeneration. The drafting sub-workflow runs once
  per execution and its contract is unchanged apart from the audience.
- **An `AUDIENCE` column on `article_queue`** — `NONE | LOW | MEDIUM | ADVANCED`. The board intake
  writes the configured default (`NONE`); a person edits the cell per row; blank is `NONE`, so
  existing rows need no backfill. The level flows to the drafting prompt, the internal gate, the
  aspect reviewers and the improver, all from one committed definitions file,
  `prompts/article_audiences.md` — the writer's hardcoded reader paragraph moves into it.
- **Three aspects ship**: `structure` (plot, arc, fit to the chosen shape), `clarity` (terms and
  plain language at the row's audience level), `flow` (redundancy, transitions, pacing), declared
  in `datasets/article_aspects.json`. Adding an aspect is a dataset + prompt-file change, not a
  graph change.

The aspect reviewers are **advisory, never gates**: their findings are data for the improvement
agent. The only gates stay the drafting gate (objective checks), the code re-check (budget and
markers), and the human — a reviewer that *rejects* on judgement is the 14055 failure in a new
place.

## Capabilities

### Modified Capabilities

- `content-writer`: a draft is improved by aspect reviewers and an improvement pass before it
  reaches the human review; a human retry edits via the improvement pass, handed the draft the
  human read; drafting, the internal gate, the aspects and the improvement are audience-aware.
- `content-backlog`: an imported row carries the lane's audience default.

## Impact

- **`agents/n8n/workflows/article_content_writer.workflow.json`**: the improvement chain is
  inserted between `check_draft_error` and `derive_slug` (~13 nodes: five prompt/config
  downloads, the aspect fan-out, the improvement agent, the objective re-check, the convergence
  node), the retry edge rewires, and `derive_slug` / `store_draft` / `draft_to_file` read the
  converged draft instead of `execute_article_creator`. Both graph copies.
- **`agents/n8n/workflows/article_creator.workflow.json`**: `main_trigger` declares `AUDIENCE`,
  `download_article_prompt` and `download_article_review_prompt` inject the level and the
  definitions. Both graph copies.
- **`agents/n8n/workflows/content_board_curator.workflow.json`**: `build_intake_rows` carries
  `AUDIENCE`, `append_article_queue` writes it. Both graph copies.
- **New files**: `prompts/article_audiences.md`, `prompts/article_improver.md`,
  `prompts/article_aspect_structure.md`, `prompts/article_aspect_clarity.md`,
  `prompts/article_aspect_flow.md`, `datasets/article_aspects.json`.
- **Edited files**: `prompts/article_writer.md`, `prompts/article_writer_system.md`,
  `prompts/article_review.md`, `datasets/board_intake.json`.
- **`article_queue`**: one new column, `AUDIENCE`, added by hand to the sheet page.
- **`agents/n8n/scripts/`**: `test_article_entry_point.py`, `test_article_prompts.py`,
  `test_article_review_gate.py`, `test_content_board_curator.py` extended; new
  `test_article_aspects.py`. `test_model_timeouts.py`, `test_prompt_sources.py`,
  `test_workflow_invariants.py`, `test_code_nodes_parse.py` sweep the new nodes automatically.
- **Cross-change**: `carry-the-draft-into-the-human-retry` (archived 2026-10-20) owns the article
  retry wiring this change rewires; its article-half test moves here and its requirement still
  holds — the receiver of the carried draft becomes the improvement pass. The LinkedIn half is
  untouched.
- **No cluster change.** No new credentials, no new DataTables, no bytes moved (the pass is
  prose; the queue-mode binary trap does not apply).

## Non-Goals

- The LinkedIn post lane: `content_queue`, `LinkedIn Post Creator`, its prompts and its retry.
- Making the aspect reviewers gates. Findings advise; nothing rejects but the objective checks
  and the human.
- Changing the internal drafting gate's checks, its bound, or the drafting agent's tool surface.
- Judging the audience at intake. A board idea is a person's decision; the intake writes the
  default and a person edits the cell.
- Backfilling `AUDIENCE` on existing rows — blank already reads as `NONE`, today's reader.
- Removing or weakening the human approval. Every round, improved or not, waits for it.
