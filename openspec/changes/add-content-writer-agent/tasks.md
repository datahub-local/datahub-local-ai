# Tasks

## 1. Content planner queue

- [x] 1.1 Add an `article_queue` page to the `content_planner` sheet with headers `ENTRY_ID, TOPIC, DESCRIPTION, LINK, CATEGORIES, ASSET_TYPES, MAX_WORDS, EXTRA_PROMPT, PRIORITY, ORIGIN, STATUS, ARTICLE_STATUS, ARTICLE_ROUND, ARTICLE_FEEDBACK, ARTICLE_TITLE, ARTICLE_REF, PUBLISHED_URL, COMMIT_REF, PUBLISHED_AT, EXECUTION_ID, ERROR, UPDATE_DATE` (no `IMAGE_*`, no `ARTICLE_TEXT`); `ASSET_TYPES` defaults to `image,svg` when blank and `MAX_WORDS` defaults to 1200; verify the page is readable by a Google Sheets node using the existing `content_planner` document id and credential (no new connection)
  **Verified live 2026-10-16.** A temporary 2-node probe (`zz_article_queue_probe_temp`, webhook -> Google
  Sheets read, created, activated, POSTed and deleted; nothing left live) read the page with the
  entry point's own document id and credential (`googleSheetsOAuth2Api` `pGARJmt50qz64xOo`, no new
  connection) and answered `200` with one row. Every one of the 22 headers is present and no
  `IMAGE_*` or `ARTICLE_TEXT` column exists. The page's column order differs from the list above
  (`STATUS` sits fourth, before `LINK`) and that is harmless: every node addresses columns by name,
  and `pick_candidate` reads `STATUS` from the item rather than a position.
- [x] 1.2 Seed one test row with a topic, a description, an optional link and `STATUS=QUEUE`, and record its `row_number`; verify the row is returned by a read node configured like `read_articles_sheet` in `linked_in_post_sharing.workflow.json`
  **Verified live 2026-10-16 by the same probe read.** `row_number: 2`, `ENTRY_ID:
  f2a53c10-6b41-4d2e-9f77-1c0a5b8e3d21`, `TOPIC: "Sympozium: a Kubernetes-native coordination layer
  for multi-agent systems"`, a `DESCRIPTION`, `LINK` to the project's README, `CATEGORIES: OSS`,
  `ASSET_TYPES: image,svg`, `MAX_WORDS: 1200`, `PRIORITY: HIGH`, `ORIGIN: manual`, `STATUS: QUEUE`
  and every lifecycle column blank. The probe's read node carries the entry point's own
  `dataLocationOnSheet` (`detectAutomatically` / `readRowsUntil: firstEmptyRow`), so the row is
  what `pick_candidate` will see.
- [x] 1.3 Create the `article_drafts` (keyed by `ENTRY_ID`) and `article_assets` (keyed by `ENTRY_ID` + `ASSET_TYPE`) n8n DataTables and store the draft and each asset's review state there; a missing table is a loud error rather than an empty article or asset. **The setup step can be automated**: the public API has DataTable endpoints after all — `GET /api/v1/data-tables` lists them and `POST /api/v1/data-tables` created and `DELETE /api/v1/data-tables/{id}` removed a probe table (201/204, measured 2026-10-16, no residue), so the earlier [UNVERIFIED] is resolved in favour of support, and the `dataTable` node itself also carries `row:upsert` and `table:create`. Created live 2026-10-16 with `POST /api/v1/data-tables`: `article_drafts` = `aMcLlyOIWTk8BhxO` (ENTRY_ID, ROUND, TITLE, SLUG, ARTICLE_TEXT) and `article_assets` = `1eE2kWVNSlS1fM25` (ENTRY_ID, ASSET_TYPE, STATUS, ROUND, S3_KEY, CONTENT_TYPE, ERROR, PATH, DATA_BASE64). The pipeline reaches them by name, so the ids are recorded here for HCL/`kubectl`-free re-creation rather than pasted into the graph
  **Re-read live 2026-10-17 and corrected.** `GET /api/v1/data-tables` answers `article_drafts` =
  `4Lu9MhBIY4G3zHon` (ENTRY_ID, ROUND, TITLE, SLUG, ARTICLE_TEXT, **LINK_USED**) and
  `article_assets` = `1eE2kWVNSlS1fM25` (ENTRY_ID, ASSET_TYPE, STATUS, ROUND, S3_KEY,
  CONTENT_TYPE, ERROR, PATH, DATA_BASE64). The draft table's earlier id was stale and its column
  set did not carry `LINK_USED`, which `store_draft` writes — so that table was recreated after
  this note was written, and the live one is what the graph needs. Nothing depends on the ids:
  every `dataTable` node in the entry point addresses its table with `mode: "name"`, which is why
  the drift was invisible.
- [x] 1.4 Enforce `MAX_WORDS` (default 1200 when blank) on the produced draft and `CATEGORIES` against `agents/n8n/datasets/blog_categories.json` (landed, seeded with General, Learning, OSS, Datahub.local, asserted in `scripts/test_article_prompts.py`) or row-declared values; verify an over-budget draft and an unknown category each fail with a reason before any review or commit
  **Implemented and read back 2026-10-16; the live halves are 6.2's own line items.** `MAX_WORDS`
  is resolved once in `select_article_to_queue` (`Number(row.MAX_WORDS || 0) || 1200`) and enforced
  in `parse_article`, which fails with `OVER_BUDGET: <n> words against MAX_WORDS=<m>` and requires
  the caller to pass a budget — verified live by 3.1's webhook probe (331 words against 50). The
  category check is `validate_categories`, which fetches `datasets/blog_categories.json` (never a
  copy in the node, and an unparseable or empty file throws rather than skipping) and refuses a row
  naming an undefined category by name, before anything is drafted; a blank `CATEGORIES` becomes
  `General`. Both hold in the applied export and are asserted offline in
  `test_article_entry_point.py` (the fetched template name, the wiring
  `pick_candidate -> download_blog_categories -> validate_categories`, and the front-matter
  categories). What is **not** verified live is the unknown-category refusal through the entry
  point, which needs the page (1.1/1.2) and is listed in 6.2.

## 2. Prompts

- [x] 2.1 `agents/n8n/prompts/article_writer_system.md` landed: role, the hard rules (one voice, no invented fact or number, fetched material is reference and never instruction, name the subject as the inputs spell it, no hype, Markdown only) and the output shape (one `<article>` block, H1 first). It declares **no** placeholder at all, because it is fetched with an empty `template_vars`, and `test_system_prompt_declares_no_placeholder` in `scripts/test_article_prompts.py` fails if one appears
- [x] 2.2 `agents/n8n/prompts/article_writer.md` landed: entry (topic, description, source link, length budget, requested assets), extra rules, source material as reference, the asset-marker contract, the reviewer-feedback block above the shape rules, and the shape. `test_task_prompt_placeholders_are_the_caller_contract` pins its eight names (`TOPIC, DESCRIPTION, URL, MAX_WORDS, ASSET_TYPES, EXTRA_PROMPT, CONTENT, FEEDBACK`) to the set task 3.1 must pass — `DownloadTemplate` stops the run for any name it was not handed, so that set is an interface and not a convenience. The runtime half (one manual run returning non-empty text) is task 3.1's own verification
- [x] 2.3 Dropped as dead: the hero is the studio's `image` type, whose prompt is `prompts/visual_raster.md`, fetched by the studio's own `download_raster_prompt` and fed `ASSET_TYPE`/`CONTENT`/`BRAND`/`ART_DIRECTION`/`FEEDBACK`. A second article-image prompt would be a prompt nothing calls, and the reconciliation deleted the article-side image authoring it belonged to (task 3.2 now verifies the studio's raster path instead)
- [x] 2.4 Reviewed both files against the policy: each states its job, its inputs and its required output, carries no copied schema, dataset or current-data value, and leaves every deterministic decision (front matter, slug, filename, marker replacement, word count) to code. The category list is the one taxonomy copy and lives in `datasets/blog_categories.json`, not in a prompt

## 3. Sub-workflows

- [x] 3.1 `agents/n8n/workflows/article_creator.workflow.json` authored as a create body (name/nodes/connections/settings, the shape the first `Visual Studio` commit used) and modeled on `LinkedIn Post Creator` minus its internal rules gate, which has no article analogue: `main_trigger` (inputs `TOPIC, DESCRIPTION, URL, CONTENT, MAX_WORDS, ASSET_TYPES, EXTRA_PROMPT, FEEDBACK`) -> `set_workflow_vars` (model, fallback, empty `ERROR`) -> `download_article_prompt` / `download_system_prompt` -> `create_article_ai` (system message from the persona file, `needsFallback`) -> `parse_article` -> `set_output` (`text`, `title`, `word_count`, `ERROR`). `parse_article` takes the `<article>` block, splits the H1 off as `TITLE`, and fails loudly on an empty body, a missing H1 or an over-budget body (it requires `MAX_WORDS`, because the default belongs to the caller). Asserted offline in `scripts/test_article_prompts.py`: the two prompt files it fetches, the vars it passes equal the task prompt's placeholders exactly, the trigger declares every input, no `settings.errorWorkflow`, and the budget codes. Created live as `nPBkIpeObC1Om0LH` and **verified by a temporary webhook probe** (workflow `zz_article_creator_probe_temp`, created, activated, POSTed, deleted — nothing left live). Three runs: a good one answered `TITLE: Running dbt on Trino and DuckDB from One Repository`, `REPORTED_WORDS`/`COUNTED_WORDS` both 216, markers `[image, svg]`, `ERROR: ''`; a forced 331-word draft against `MAX_WORDS=50` answered `ERROR: OVER_BUDGET: 331 words against MAX_WORDS=50` with the text still returned; an omitted `MAX_WORDS` failed the sub-run at `parse_article` with `MAX_WORDS is required and must be a positive number`. The first attempt 404'd at `download_template`: `DownloadTemplate` reads the prompts from the backup repo's **main**, so the files had to be pushed before a run could fetch them
- [x] 3.2 Verified live through the existing test harness: `POST /webhook/visual-studio-test` with `ASSET_TYPES=image` answered `RUN_STATUS: COMPLETE`, one asset with `ASSET_TYPE: image`, `STATUS: RENDERED`, `FORMAT: png`, `CONTENT_TYPE: image/png`, empty `S3_KEY` (the raster branch carries its own bytes) and a download link. The link served 943,620 bytes of `image/png` from both the in-cluster service and the public host, magic `89504e470d0a1a0a`, IHDR 928x1152 — so the hero is a real PNG, and that byte count is what the raster path costs in the studio's execution record. Original wording: call `Visual Studio` with `ASSET_TYPES=image` and confirm the answer carries one asset whose `STATUS` is `RENDERED`, whose `FORMAT` is `png`, and whose inline data URL decodes to a PNG (no image authoring is added in this change; the studio's `image` branch owns it)
- [x] 3.3 Verified live, both paths. A diagnosable failure comes back as data: the forced over-budget run returned `ERROR: OVER_BUDGET: ...` with the draft, which is what `check_subworkflow_error` branches on. A hard failure propagates instead of returning a benign empty result: with `MAX_WORDS` omitted, `parse_article` threw, the sub-execution 13487 ended `error` at that node, the caller's `executeWorkflow` node failed and the webhook answered 500 — so the run cannot end `success` with no items. The invalid-model-id variant was not probed separately: it is the same mechanism on the `chainLlm` node, which carries no `onError`, and `set_output` always carries the `ERROR` field so the caller never infers failure from a missing item.

- [x] 3.4 `agents/n8n/workflows/content_research.workflow.json` authored and created live as `3YctNv7fJl17sOT3` (**active**, no trigger that fires on its own): `main_trigger` (`QUERY`) -> `normalize_input` (a blank query is refused by name) -> `search_hn` (Hacker News Algolia) and `search_feeds` (Miniflux `/v1/entries?search=`, reusing the curator's own env vars and base64 auth idiom) in parallel -> `build_digest` (one digest that names which sources answered, `alwaysOutputData`). Both searches carry `onError: continueRegularOutput` **and** a node note: a failure forwards the node's input unchanged, so the digest reads each source by node name and reports `Unavailable this run: ...` instead of hiding it. Neither source needs an API key — this deployment holds no search-credential. Contract asserted offline in the new `scripts/test_content_research.py` (9 tests: trigger, blank query, keyless sources, the report-a-dead-source wiring, `alwaysOutputData`, the fan-out, a sub-workflow that raises, and that the writer's tool points at this file's own id)

## 4. Entry-point workflow

- [x] 4.1 `agents/n8n/workflows/article_content_writer.workflow.json` authored as a create body (73 nodes) and every sheet node rewired to the `article_queue` page — addressed by name, since the page does not exist yet and the node's own builder hint says a title in `list` or `id` mode cannot resolve (export authored; offline assertions in `scripts/test_article_entry_point.py`; the live run is 6.2)
- [x] 4.2 `pick_candidate` picks the one entry (QUEUE first, then the oldest mid-flight claim), `read_asset_rows_for_entry` reads that entry's asset rows by `ENTRY_ID`, `select_article_to_queue` turns both into the `PHASE` + `PENDING_ASSETS` the graph switches on, and `update_status_in_progress` writes `STATUS=IN_PROGRESS` and `EXECUTION_ID=$execution.id` before the first model call (export authored; offline assertions in `scripts/test_article_entry_point.py`; the live run is 6.2)
- [x] 4.3 `if_has_link` skips the fetch, and `set_link_flags` always emits one item carrying `LINK_USED` + the fetched text. The flag is set there and never read from the failed node's output: a non-AI node with `continueRegularOutput` forwards its input unchanged, so `$json.error` is absent and a branch on it would take the success path (export authored; offline assertions in `scripts/test_article_entry_point.py`; the live run is 6.2)
- [x] 4.4 Article phase wired: `execute_article_creator` (with `MAX_WORDS` resolved to 1200, the row's `ASSET_TYPES`, `SESSION_ID` from the entry and the retry's `FEEDBACK`) -> `check_draft_error` (a failed draft reaches `fail_draft`, and no Slack node is reachable from it) -> `derive_slug` (the slug frozen here, stored in the draft row) -> `store_draft` (upsert into `article_drafts`) -> `draft_to_file` -> `upload_draft_file` (the draft as a Slack file, because `sendAndWait` truncates around 3000 characters) -> `update_article_drafted` (round, title, `ARTICLE_REF`, `STATUS=WAITING_APPROVAL`) -> `notify_article_review` -> `switch_article_accept` -> retry form -> `switch_article_retry` -> back to the creator, or `update_status_cancelled` -> `retire_asset_rows` -> notice (export authored; offline assertions in `scripts/test_article_entry_point.py`; the live run is 6.2)
- [x] 4.5 Asset phase wired by calling `Visual Studio` as a sub-workflow with `(CONTENT from the draft, ASSET_TYPES from the row or image,svg, FEEDBACK from the asset's row, SESSION_ID from the entry)`; read each asset's own `STATUS`/`ERROR` rather than the run `STATUS`, fetch an agent asset's bytes from its `S3_KEY` through `temp_retrieve` and the raster `image` asset from its inline data URL, write each asset's state (type, status, round, feedback, key, committed path) to the `article_assets` DataTable, send each to Slack for its own approval, and verify rejecting one asset preserves the others' approvals and that a type the registry does not declare reports as that asset's error without taking the rest of the set with it
- [x] 4.6 Publish step implemented against the Git Data API (get ref, create one blob per file, create tree, create commit, patch ref) with a slug derived and disambiguated via `GET contents/docs/blog/posts`, each asset written to `docs/img/<frozen-slug>-<type-id>.<ext>` and referenced at its `<!-- asset:<type> -->` marker (default position when absent), front-matter composed in a Code node, and `PUBLISHED_URL` computed as the blog plugin's `https://alvsanand.com/blog/<YYYY>/<MM>/<DD>/<title-slug>/`; on a non-fast-forward `PATCH ref`, re-fetch the ref and retry once without force-pushing; persist `PUBLISHED_URL`, `COMMIT_REF`, `STATUS=PUBLISHED` and each asset's path; verify exactly one commit contains the article and all approved assets and no commit is made while any requested supported asset is unapproved
- [x] 4.7 `send_published_notification` names the URL, the commit and the file count, and both cancel branches notify: the article's (`update_status_cancelled` -> `retire_asset_rows` -> notice) and one asset's (`mark_asset_cancelled` -> notice, which says the article stays as approved) (export authored; offline assertions in `scripts/test_article_entry_point.py`; the live run is 6.2)
- [x] 4.8 The publish nodes reuse the existing n8n GitHub credential (`githubApi` `x1DjxYsMLFm3vUiv`, "GitHub account"). Its reach was measured on 2026-10-16 through a temporary probe workflow that called `GET /repos/alvsanand/alvsanand` with that credential and was deleted after: GitHub answered `permissions {admin, maintain, push, triage, pull}` and the credential reports the classic scopes `repo, write:packages`. It can publish, and it is **not** scoped to one repository — `repo` reaches everything that account can push to, so the change's own risk mitigation applies (mint a fine-grained token with `contents: write` on `alvsanand/alvsanand`, or accept that the bound is the workflow's own URLs, which name that repository and nothing else). The workflow-side half is bounded: every GitHub call in the graph names `alvsanand/alvsanand`. Remaining: the scratch-branch write (POST `/git/refs`, then delete the ref) and the decision above
  **Decided by the owner 2026-10-16: the classic `repo` credential stays; the bound is the graph.**
  Every GitHub call in `article_content_writer.workflow.json` names `alvsanand/alvsanand` and
  nothing else, so the practical reach is that repository, and swapping the credential buys a
  secret to rotate rather than a smaller capability. Recorded rather than mitigated. The
  scratch-branch write stays unprobed: the commit sequence is 4.6's own path (get ref, blobs,
  tree, commit, patch ref) and the first real publish (6.3) exercises it on `main`, so a
  throwaway ref would prove nothing the publish does not.
- [x] 4.9 Marker contract implemented in `build_commit_files`: the article prompt emits one `<!-- asset:<type> -->` per requested type and the commit step replaces each with the reference and alt text; verify a missing marker is placed at the default position and the asset is still committed — not hypothetical: of three live drafts (task 3.1's probe), one answered the `image,svg` request with `<!-- asset:image -->` only, so the default placement is the half that keeps a requested asset from vanishing
- [x] 4.10 The slug is derived once at the first draft and stored on the draft row (`article_drafts.SLUG`), not in `ARTICLE_REF` — that cell keeps pointing at the draft rather than carrying two facts. A retry reuses the stored slug; the commit disambiguates it against `docs/blog/posts` only when it would collide, which is still before anything is committed (export authored; offline assertions in `scripts/test_article_entry_point.py`; the live run is 6.2)
- [x] 4.11 Ownership confirmed by graph inspection: the entry point holds every `sendAndWait` gate and the only commit sequence, and both sub-workflows are called with their own contracts and no `settings.errorWorkflow`. Asserted offline rather than read once (export authored; offline assertions in `scripts/test_article_entry_point.py`; the live run is 6.2)
- [x] 4.12 The predicate is `select_article_to_queue`'s `PHASE` over the sheet row plus the entry's asset rows; the claim is single-flight because only `QUEUE -> IN_PROGRESS` races; a resumed run re-reads the draft from `article_drafts` and asks the studio for `PENDING_ASSETS` only, so an approved asset is never re-authored; and cancelling retires the entry's asset rows in the same step (export authored; offline assertions in `scripts/test_article_entry_point.py`; the live run is 6.2): a run determines its next action from the predicate, skips an entry held by a live run, re-presents a pending review from stored state without regenerating an approved artifact, and cancels an entry's non-terminal asset rows when the entry is cancelled; verify every predicate row, two overlapping manual runs, a simulated dead run, and a cancelled entry leaving no live asset row

- [x] 4.13 The writer is an agent with two tools (D18). `create_article_ai` is `@n8n/n8n-nodes-langchain.agent` 3.1, with the persona and the task prompt merged into its `text` (the node's system slot is a parameter this repository has never used, and one wrong key would drop the persona silently), `needsFallback` and `maxIterations: 12`; its tools are `research_sources` (workflow tool -> `Content Research`) and `read_page` (workflow tool -> `Download Content`), both `toolWorkflow` v2. The first version used two `toolHttpRequest` tools and **every call failed** — `has a "supplyData" method but no "execute" method` — taking the draft with it (`EMPTY_DRAFT`, execution 13598), so `test_every_writer_tool_can_be_executed_by_the_agent` pins the tool types to those measured to implement `execute` and `test_task_prompt_bounds_and_scopes_the_research` pins the prompt's three-lookup bound, its same-named-source rule and its read-before-cite rule. `toolWikipedia` was wired, probed and dropped (it answered a Dimmu Borgir album for "Sympozium"). The sub-workflow's external contract (`text`, `title`, `word_count`, `ERROR`) is unchanged so the entry point needs no edit, and `parse_article` reads `output` **or** `text`, because an agent answers the former where a chain answered the latter
- [x] 4.14 A fresh entry can be phased, and the first live run proved it could not. The DataTable read
  that loads an entry's asset rows emits **nothing** when the entry has none — the normal state of a
  row that has never been drafted — and n8n ends the execution on an empty output, so
  `select_article_to_queue`, which is what decides the phase, never ran. Found by the first live run
  of a `QUEUE` row (execution 13703, 2026-10-17): `read_article_queue` read 198 rows, `pick_candidate`
  picked row 2, `validate_categories` passed, `read_asset_rows_for_entry` `in=0 out=0` and
  `lastNodeExecuted` was that node; the run reported `success`. (The run before it, 13702, ended at
  `pick_candidate` for a different reason: the row's `STATUS` was `CANCELED` at that moment, which is
  the filter working.)
 **Landed.** `read_asset_rows_for_entry` carries `alwaysOutputData: true`, so the empty read emits one
 item and the phase is decided from stored state rather than from a node that silently ends the run.
 `select_article_to_queue` already tolerates it — an item with no `ASSET_TYPE` matches no requested
 type, so every requested asset stays pending and the phase is `draft`. Asserted by
 `test_the_asset_read_always_emits_so_a_fresh_entry_can_be_phased` (fails with `KeyError:
 'alwaysOutputData'` without the change; suite 486 passed, 1 skipped). Applied live with
 `--require-edge` on both sides of the node and read back: 75 nodes, node names equal to the export,
 `alwaysOutputData: True`, `active: False`, `activeVersionId: None`, so nothing was armed.
 One consequence of that apply is worth knowing: opening the workflow in the editor added
 `settings.binaryMode: separate` to the live draft, which no API write can produce, so live now
 differs from the export by that one field until the next 02:00 backup reconciles it.

- [x] 4.15 The article's hero is framed for a screen, and the frame is the type's data in both
  halves of the raster branch. Found by the first live asset run (2026-10-17): the hero came back
  928x1152 (4:5) and the animated SVG 1280x1600 (4:5), because `image` and `svg` declare the
  LinkedIn feed's frame and the blog was asking for those. The frame was also fixed rather than
  declared on the raster side — `generate_image` hardcoded `aspect_ratio: "4:5"` while the director
  it had just prompted wrote *"landscape 3:2"*, so the model composed one shape and the API
  cropped it to another (read out of execution 13712)
 **Landed (export + registry + prompt; the graph half is 4.17).** `datasets/visual_types.json`
 gains `image_wide` and `svg_wide`, both 16:9 — the same media at the frame a page wants, so the
 LinkedIn types keep 4:5 and no request parameter was added. `generate_image`'s `aspect_ratio` is
 now `$('if_raster').all()[$itemIndex].json.ASPECT` (the chain node emits only `{text}`, so
 `$json` cannot carry it and `$itemIndex` is the pairing) and `download_raster_prompt` passes
 `ASPECT` into `prompts/visual_raster.md`, which composes to it — the registry and the prompt are
 read from GitHub `main`, so those two halves are live on push. Both copies of the studio graph
 carry the change (`nodes` and `activeVersion.nodes`; patching one is how this was caught).
 Asserted by `test_the_wide_types_are_the_landscape_frame` and
 `test_the_raster_frame_comes_from_the_type` (the latter fails on the hardcoded `4:5`).
- [x] 4.16 A blocked publish reports instead of ending the run with nothing. `if_all_assets_approved`
  was a Code node that `return []`ed when any requested asset was not approved or had no row, and
  n8n ends the execution on an empty output: execution 13705 ended `success` with no commit and no
  Slack line, and the reason (`svg=MISSING`) existed only in the execution log
 **Landed (export; the graph half is 4.17).** The gate now emits `BLOCKED`/`BLOCKING` as data, and
 `if_assets_blocked` routes: blocked → `notify_assets_blocked` (a Slack *message*, not a wait, so a
 blocked publish cannot park the run), clear → `read_asset_rows_for_publish`. Asserted by
 `test_the_blocked_publish_reports_instead_of_ending_the_run`, which also pins that nothing
 continues from the notice into the commit and that it carries the same channel and credential as
 its neighbours. Both new tests fail without the change.
- [ ] 4.17 Apply the graph halves live and point the test row at the wide pair. The studio's
  `aspect_ratio` + `ASPECT` template var and the entry point's wide defaults, new `if_assets_blocked`
  /`notify_assets_blocked` pair and rewiring are graph changes: the registry and the prompt are live
  on push, these are not. The row's `ASSET_TYPES` (`image,svg` today) is a sheet edit — the flow's
  own fallbacks now name the wide pair, so a row that declares the portrait types still asks for
  them, which is the intended override rather than a bug.
 **Applied live 2026-10-17; the push and the sheet edit remain.** Both graphs were applied with
 `--require-edge` guards and read back. `Visual Studio`: the draft carried both fields and the
 **published** version was fetched by its version id to confirm it too (29 nodes, `aspect_ratio`
 expression, `ASPECT` present) — a PUT edits the draft, and the article path runs the published
 sub-workflow, so publishing was the half that made it real. `Article Content Writer`: 77 nodes,
 the two new nodes present, both rewirings confirmed, `active: False`. Live vs export: node-name
 and connection hashes equal for both workflows, and every parameter of every touched node equal;
 the only differences are `settings.binaryMode` and node positions, both UI-owned and reconciled by
 the 02:00 backup.
 **One coupling had to be closed before applying.** The hero rule is duplicated in
 `select_article_to_queue` and in the publish gate, and a gate that prepends a type the selector did
 not ask for blocks every run forever. Both now read the same predicate: either raster counts as a
 declared hero, and a row that names neither gets `image_wide`.
 **The push is required before the next run**: `datasets/visual_types.json` and
 `prompts/visual_raster.md` are fetched from GitHub `main` by `DownloadTemplate`, so an uncommitted
 `image_wide` is `unknown asset type: image_wide` at the studio and both assets come back `UNKNOWN`.
 **The stale row was removed** for the chosen reset: `article_assets` held one APPROVED `image` row
 (portrait, round 1) for entry `f2a53c10-…`, deleted with
 `DELETE /api/v1/data-tables/1eE2kWVNSlS1fM25/rows/delete?filter=…` (filter required by the API,
 200, the entry now has no asset rows). The row's `STATUS=QUEUE` and `ASSET_TYPES=image_wide,svg_wide`
 are the owner's edit, and `ENTRY_ID` is kept so the approved draft is reused.
 **Found while doing it, not fixed here:** `build_commit_files` commits *every* row the entry has,
 not only the requested types, so a leftover APPROVED row of a type no longer requested would be
 committed as an extra asset. It is why the stale row had to go, and it wants its own fix: the
 commit path should read the requested set the gate already computes.

- [x] 4.18 A type can pin the composition form it means. The registry had no form field, so a
  diagram could only be *hoped* for: `FORCE` is one value per request, and the article's brief
  sends none, leaving the choice to the composer (it picked `diagram` for this subject, by choice
  rather than by contract)
 **Landed and live 2026-10-17.** `datasets/visual_types.json` gains an optional `form` (with its
 `_comment_form`), `svg_wide` declares `diagram`, `parse_registry` shapes `FORM: t.form || ''`
 (and the unknown/unavailable note carries the field too), and `build_author_brief` resolves
 `a.FORM || req.FORCE || 'auto'` — the type wins, then the caller, then the composer. Applied to
 `Visual Studio` with `--require-edge` on the registry→brief path and **published**; the published
 version (`933d8e1c…`) carries both. Asserted by `test_a_type_may_pin_the_form_it_means` (the
 declared form must be a name in `prompts/visual_forms.md`, so a typo cannot reach the composer as
 prose) and `test_a_types_form_is_honoured_ahead_of_the_callers`; both fail without the change.
 One guard earned its keep here: the first apply was refused by
 `--require-edge 'normalize_input>build_author_brief'`, an edge that does not exist
 (`normalize_input -> download_brand`), so a premise I had assumed was checked rather than
 written.

## 5. Error handling

- [x] 5.1 `agents/n8n/workflows/article_content_writer_error.workflow.json` authored as a create body, modeled on `linked_in_post_sharing_error` with one deliberate divergence: the row match no longer decides whether the notice is sent. `select_row_with_error` emits a `NO_ROW` item when nothing carries the failed execution id, `if_row_found` sends the matched row through the Sheet update and the rowless case straight to `set_error`, and both paths reach `send_error_notification` — the LinkedIn shape ends the notice on the row match, so a failure with no matching row is silent. Offline assertions in `scripts/test_content_writer_graph.py` (the handler sets no `errorWorkflow`, the notice is reachable from the trigger and from the rowless branch, only the matched branch updates the sheet, the page is addressed by name). No `settings.errorWorkflow` on the handler itself, per the repo rule. **Remaining: the live trigger** (the row moves to `ERROR` and the notice is delivered) — needs the page and the entry point to exist, so it is part of 6.1/6.2
- [x] 5.2 Wired live: `Article Content Writer Error` created as `33uWLrAzZMm4SOP8` and **activated** (a handler that is not active cannot fire), `settings.errorWorkflow` set on `Article Content Writer` (`sKsjxDDW40TATaS6`) with `--require-edge click_trigger>read_article_queue`, read back as `33uWLrAzZMm4SOP8` with no mismatch, and the entry point left `active: False` so the schedule cannot tick (6.6). `test_article_entry_point.py` now asserts the setting equals the handler export's own id rather than restating it
- [x] 5.3 `scripts/apply_workflow_changes.py` already carries the idempotent `--create` (POST a workflow body once, keyed by name, print the new id; `--dry-run` prints the plan; only `name`/`nodes`/`connections`/`settings` are read from the body) and `agents/n8n/scripts/test_apply_workflow_changes.py` covers creating when absent, leaving a same-named workflow untouched, and the dry run — it landed when `Visual Studio` was created with `--create /tmp/vs.json`. What remains for this change is only to use it, which is task 6.1

## 6. Apply and verify

- [x] 6.1 Create and apply all new workflows live with `scripts/apply_workflow_changes.py --create` after showing the diff, pairing subsequent edits with `--require-edge`, and re-read to confirm each field landed; verify the live graph matches the exports. `Article Creator` done: created as `nPBkIpeObC1Om0LH`, activated, read back and diffed (9 nodes and the connections identical, both graph copies agreeing), and the export rewritten to the canonical backup shape (the `GET /api/v1/workflows?limit=250` entry with sorted top-level keys, which is what the backup itself writes — verified against `visual_studio.workflow.json`). One field of the create body did not land: `settings.binaryMode`, which the public API accepts on neither `POST` nor `PUT`; it was dropped from the export and the measurement recorded in `AGENTS.md`. Created live 2026-10-16: `Article Creator` `nPBkIpeObC1Om0LH`, `Article Content Writer Error` `33uWLrAzZMm4SOP8` (active), `Article Content Writer` `sKsjxDDW40TATaS6` (inactive, by 6.6). Every export is the canonical backup shape (the `GET /api/v1/workflows?limit=250` entry, top-level keys sorted), which the 02:01 backup reproduced byte-for-byte for `Article Creator`. Still missing before 6.2 can run: the `article_queue` page and its test row (1.1, 1.2), which only a human can add

- [ ] 6.2 Exercise every path with the manual trigger: article+all assets approved, one asset rejected then retried (confirming the retry edits the entry's session rather than authoring a new composition), article rejected then retried, an asset-only reject after the article is approved, a text-only tweak (every pending review still re-opens), a long draft reviewed without truncation (file/snippet, not inline), a resumed review carrying its round in the same thread, a `ASSET_TYPES` value naming a type the registry does not declare (that asset reports its error and the rest of the set proceeds), a concurrent commit on `main` retried once, an over-budget draft, an unknown category, and cancel (asset rows retired); verify the observable row/asset state and Slack messages for each

- [ ] 6.3 Verify the end-to-end publish: the article and all its approved assets land in `alvsanand` in one commit, `docs/blog/posts/<YYYYMM>-<slug>.md` has valid front-matter and references each asset at its marker with alt text, each asset row records its committed path, and the entry records URL and commit ref
- [ ] 6.4 Verify idempotency by running the trigger again for the published test row; confirm no commit, no asset and no row change
- [ ] 6.5 Verify a source link that cannot be fetched continues from topic/description and records that the link was not used
- [ ] 6.6 Keep the schedule inactive and run by manual trigger until 6.2–6.5 pass, then activate the schedule and confirm the next tick selects at most one `QUEUE` row and processes no more than one entry per trigger
 **Deactivated again 2026-10-18, deliberately.** The entry point was found live `active: True` with
 its `0 0 8 * * 2,4` cron armed, and the export had recorded `True` in every backup since
 2026-10-18 02:00 (`4c1bfb0`) against `False` before that — so it was activated on the instance on
 2026-10-17/18, with 6.2–6.5 still open and the next tick two days out. `POST
 /api/v1/workflows/sKsjxDDW40TATaS6/deactivate` answered `200`, the read-back is `active: False,
 activeVersionId: null` with all 78 nodes intact, and the export still says `True` until the 02:00
 backup reconciles it. Re-arm only when 6.2–6.5 have passed.
- [ ] 6.7 Verify the research path through the entry point, on one row each: (a) a subject the web has — the draft cites a page the writer fetched during the run and cites nothing else; (b) a subject it does not — the draft cites nothing, says no source was found, and is still produced. Both were exercised against `Article Creator` by probe and are recorded in the design's measurements; this task is the same two runs end to end, where the row state and the Slack review are part of the evidence. Also record how often `ai_model` fails on a tool-attached call and whether any run exhausts `maxIterations`
