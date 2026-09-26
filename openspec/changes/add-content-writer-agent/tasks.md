# Tasks

## 1. Content planner queue

- [ ] 1.1 Add an `article_queue` page to the `content_planner` sheet with headers `ENTRY_ID, TOPIC, DESCRIPTION, LINK, CATEGORIES, ASSET_TYPES, MAX_WORDS, EXTRA_PROMPT, PRIORITY, ORIGIN, STATUS, ARTICLE_STATUS, ARTICLE_ROUND, ARTICLE_FEEDBACK, ARTICLE_TITLE, ARTICLE_REF, PUBLISHED_URL, COMMIT_REF, PUBLISHED_AT, EXECUTION_ID, ERROR, UPDATE_DATE` (no `IMAGE_*`, no `ARTICLE_TEXT`); `ASSET_TYPES` defaults to `hero_static,infographic_static` when blank and `MAX_WORDS` defaults to 1200; verify the page is readable by a Google Sheets node using the existing `content_planner` document id and credential (no new connection)
- [ ] 1.2 Seed one test row with a topic, a description, an optional link and `STATUS=QUEUE`, and record its `row_number`; verify the row is returned by a read node configured like `read_articles_sheet` in `linked_in_post_sharing.workflow.json`
- [ ] 1.3 Create the `article_drafts` n8n DataTable keyed by `ENTRY_ID` and store the draft there; document its creation as a setup step, treat a missing table as a loud error rather than an empty article, and record that Data Tables API support is [UNVERIFIED]
- [ ] 1.4 Enforce `MAX_WORDS` (default 1200 when blank) on the produced draft and validate `CATEGORIES` against `datasets/blog_categories.json` (seeded with General, Learning, OSS, Datahub.local) or row-declared values; verify an over-budget draft and an unknown category each fail with a reason before any review or commit

## 2. Prompts

- [ ] 2.1 Add `agents/n8n/prompts/article_writer_system.md` (role, hard rules, no invented facts, required output shape) and verify it has no unresolved `{{ }}` placeholders beyond `{{ RULES }}` and `{{ EXTRA_PROMPT }}`
- [ ] 2.2 Add `agents/n8n/prompts/article_writer.md` (long-form article instruction taking topic, description, optional source content and optional feedback, with a length budget) and verify every placeholder resolves through `DownloadTemplate`
- [ ] 2.3 Add `agents/n8n/prompts/article_image_prompt.md` (hero-image prompt builder from the article text, mirroring `linkedin_image_prompt.md`) and verify it renders through `DownloadTemplate` with the `ARTICLE_CONTENT`/`FEEDBACK` variables supplied
- [ ] 2.4 Confirm all three prompts follow the repo AI prompt policy (short, literal, no copied data or schema); verify by review against `AGENTS.md`

## 3. Sub-workflows

- [ ] 3.1 Author an `Article Creator` sub-workflow modeled on `LinkedIn Post Creator`, with inputs `TOPIC, DESCRIPTION, URL, CONTENT, FEEDBACK, MAX_WORDS, EXTRA_PROMPT`, fetching `article_writer_system.md` and `article_writer.md` via `DownloadTemplate`; verify a manual run returns non-empty `text` and an empty `ERROR`
- [ ] 3.2 Author the static-hero path (the single-element asset set until `add-visual-studio` lands), modeled on `LinkedIn Image Creator`, with inputs `ARTICLE_CONTENT, FEEDBACK, HOOK`, calling the LiteLLM image endpoint with the model used by `linked_in_image_creator`, and returning the `omImage` base64 shape plus `prompt`; verify a manual run returns a base64 payload that decodes to a PNG
- [ ] 3.3 Verify both sub-workflows propagate failures in an `ERROR` field (as `execute_post_creator` does) rather than ending with empty output, by forcing an invalid model id and observing a non-empty `ERROR`

## 4. Entry-point workflow

- [ ] 4.1 Clone `linked_in_post_sharing.workflow.json` into a new `Article Content Writer` workflow and rewire the sheet reads/writes to the `article_queue` page; verify the workflow parses and its nodes reference `article_queue`
- [ ] 4.2 Implement the `select_article_to_queue` Code node (lowest `row_number` among `STATUS=QUEUE`) and the `update_status_in_progress` node; verify one run claims exactly one row and a second concurrent run claims a different row
- [ ] 4.3 Rewire `download_content` so it runs only when `LINK` is non-empty, and records "link not used" when absent or unreachable; verify both cases
- [ ] 4.4 Wire the article phase: `execute_post_creator` -> `Article Creator`, `check_subworkflow_error`, `update_status_waiting_approval`, `notification_accept`, `switch_user_accept`, `notification_retry_or_cancel` (Retry/Cancel + Feedback), and persist `ARTICLE_STATUS`/`ARTICLE_FEEDBACK`/`ARTICLE_TEXT`; verify approve, reject-then-retry and cancel each set the expected state
- [ ] 4.5 Wire the asset phase by calling the Visual Studio sub-workflow (`add-visual-studio`) with `(ENTRY_ID, ARTICLE_TEXT from the DataTable, ASSET_TYPES)`; verify each asset gets a row in `article_assets`, each is sent to Slack for its own approval, and rejecting one asset preserves the others' approvals
- [ ] 4.6 Implement the publish step as an HTTP Request to the GitHub Git Data API (get ref, create one blob per file, create tree, create commit, patch ref) with a slug derived and disambiguated via `GET contents/docs/blog/posts`, each asset written to `docs/img/<frozen-slug>-<type-id>.<ext>` and referenced at its `<!-- asset:<type> -->` marker (default position when absent), front-matter composed in a Code node, and `PUBLISHED_URL` computed as the blog plugin's `https://alvsanand.com/blog/<YYYY>/<MM>/<DD>/<title-slug>/`; on a non-fast-forward `PATCH ref`, re-fetch the ref and retry once without force-pushing; persist `PUBLISHED_URL`, `COMMIT_REF`, `STATUS=PUBLISHED` and each asset's path; verify exactly one commit contains the article and all approved assets and no commit is made while any requested supported asset is unapproved
- [ ] 4.7 Add `send_published_notification` (published URL + commit link) and the cancel branches (`STATUS=CANCELLED`) with a Slack notice; verify each fires on its path
- [ ] 4.8 Reuse the existing n8n GitHub credential on the publish node and confirm its write scope covers `alvsanand/alvsanand` contents only; verify a publish to a scratch branch succeeds, then remove the scratch branch, and record whether the credential needed to change
- [ ] 4.9 Implement the asset reference marker contract: the article prompt emits one `<!-- asset:<type> -->` per requested type and the commit step replaces each with the reference and alt text; verify a missing marker is placed at the default position and the asset is still committed
- [ ] 4.10 Freeze the slug at first draft and bind the published URL and asset filenames to it; verify a retry that changes the title leaves the slug, the URL path and the asset filenames unchanged
- [ ] 4.11 Confirm the ownership contract by graph inspection: `Article Content Writer` runs every Slack gate and the single commit, and the Visual Studio sub-workflow is invoked with `(ENTRY_ID, ARTICLE_TEXT, ASSET_TYPES)` and performs neither
- [ ] 4.12 Implement the next-action predicate over `STATUS × ARTICLE_STATUS × asset states`, single-flight claim, resumable review, and cancel propagation: a run determines its next action from the predicate, skips an entry held by a live run, re-presents a pending review from stored state without regenerating an approved artifact, and cancels an entry's non-terminal asset rows when the entry is cancelled; verify every predicate row, two overlapping manual runs, a simulated dead run, and a cancelled entry leaving no live asset row

## 5. Error handling

- [ ] 5.1 Author an `Article Content Writer Error` workflow modeled on `linked_in_post_sharing_error`: on `errorTrigger`, read `article_queue`, select the failed row, set `STATUS=ERROR` with the reason, and notify Slack; verify by triggering an error and seeing the row cleared and the notice delivered
- [ ] 5.2 Set `settings.errorWorkflow` on the `Article Content Writer` entry point and confirm the schedule trigger is not deactivated by the apply; verify the error workflow reference resolves
- [ ] 5.3 Extend `scripts/apply_workflow_changes.py` with an idempotent `--create` (POST a workflow body once, keyed by name, print the new id); verify by creating a throwaway workflow, editing it through the existing `PUT` path, then deleting it, and confirm a same-named workflow is left untouched

## 6. Apply and verify

- [ ] 6.1 Create and apply all new workflows live with `scripts/apply_workflow_changes.py --create` after showing the diff, pairing subsequent edits with `--require-edge`, and re-read to confirm each field landed; verify the live graph matches the exports
- [ ] 6.2 Exercise every path with the manual trigger: article+all assets approved, one asset rejected then retried, article rejected then retried, an asset-only reject after the article is approved, a text-only tweak (every pending review still re-opens), a long draft reviewed without truncation (file/snippet, not inline), a resumed review carrying its round in the same thread, a concurrent commit on `main` retried once, an over-budget draft, an unknown category, and cancel (asset rows retired); verify the observable row/asset state and Slack messages for each
- [ ] 6.3 Verify the end-to-end publish: the article and all its approved assets land in `alvsanand` in one commit, `docs/blog/posts/<YYYYMM>-<slug>.md` has valid front-matter and references each asset at its marker with alt text, each asset row records its committed path, and the entry records URL and commit ref
- [ ] 6.4 Verify idempotency by running the trigger again for the published test row; confirm no commit, no asset and no row change
- [ ] 6.5 Verify a source link that cannot be fetched continues from topic/description and records that the link was not used
- [ ] 6.6 Keep the schedule inactive and run by manual trigger until 6.2–6.5 pass, then activate the schedule and confirm the next tick selects at most one `QUEUE` row and processes no more than one entry per trigger
