# Proposal

## Why

The homelab already has an end-to-end, human-reviewed pipeline that turns a queued source into a published LinkedIn post with a generated image: `linked_in_post_sharing.workflow.json` reads `content_planner`, selects one article, drafts it, takes a Slack approval, generates and approves an image, then publishes. The personal blog (`alvsanand.com`) has no equivalent — the gap between "I have something to write about" and a published long-form article with a hero image is still manual. This change clones the proven n8n pattern for the blog instead of inventing a new runtime.

## What Changes

- Add a new `article_queue` page to the `content_planner` sheet, mirroring `content_queue`: rows authored outside this system carry a topic, a description, an optional source link, and a status.
- Add a new scheduled n8n workflow modeled on `linked_in_post_sharing`: read `article_queue`, select one `QUEUE` row, mark it `IN_PROGRESS`, retrieve the source content when a link is present, produce a long-form article draft, take a Slack approval, produce the entry's asset set through the existing `visual-studio` capability and approve each asset separately, then publish.
- Add one companion sub-workflow for the long-form article, mirroring `LinkedIn Post Creator`, plus new prompt files under `agents/n8n/prompts/`. Assets are not authored here: the entry point calls the `visual-studio` capability's generic workflow as a sub-workflow, so the blog and the LinkedIn lane share one asset producer.
- Review in Slack, as the LinkedIn flow does: a double approval (`sendAndWait`) for the article, and a separate double approval for each asset. A rejection opens the existing retry form (Retry/Cancel plus free-text feedback) and regenerates only that artifact with the feedback; every other artifact's approval is preserved.
- Publish only when the article and every requested asset are approved: commit them together in a single commit to the `alvsanand` repository's default branch (`docs/blog/posts/<YYYYMM>-<slug>.md` and each asset under `docs/img/`), which GitHub Pages / `mkdocs gh-deploy` then serves. Direct to `main`, so this is the first n8n workflow that writes to a repository outside the homelab.
- Record the outcome in the `article_queue` row (status, article review state, published URL, commit reference) and in a per-asset row (asset state, object key, committed path).
- Add error handling per the repo rule: the entry-point workflow carries `settings.errorWorkflow`, and a companion error workflow marks the failed row and notifies Slack.
- **No Sympozium, no MCP server, no cluster change.** Everything is n8n, the Google Sheet and the GitHub API.

## Capabilities

### New Capabilities
- `content-writer`: a scheduled, Slack-reviewed n8n pipeline that turns an `article_queue` entry into a long-form blog article and the asset set the `visual-studio` capability produces for it (a raster hero plus one diagrammatic asset by default), iterates each artifact on feedback, and commits the article and every approved asset to the `alvsanand` repository in one commit once all are approved.

### Modified Capabilities
<!-- None. No spec exists yet under openspec/specs/. -->

## Impact

- **`agents/n8n/workflows/`**: new exports for the entry-point workflow, its error workflow, and the article sub-workflow. The `visual-studio` workflow is called, not changed. Per the repo rule these are backups; the change is only live once applied with `scripts/apply_workflow_changes.py`, and every workflow needs its failure path wired before it is done.
- **`agents/n8n/prompts/`**: new prompt files for the long-form article (system + task), fetched at runtime through the existing `DownloadTemplate` workflow; they must follow the repo's AI prompt policy (short, literal, no copied data).
- **`content_planner` sheet**: new `article_queue` page and its columns. Rows are authored by a human.
- **GitHub**: a credential/token with `contents:write` scoped to `alvsanand/alvsanand`; whether the existing n8n GitHub credential already carries write scope is [UNVERIFIED].
- **`alvsanand`** (cross-repo): a push to `main` publishes through `.github/workflows/pages.yml`; post front-matter and image-path conventions must be respected.
- **No change** to `datahub-local-core`, `datahub-local-ai-mcp`, or Sympozium. The approved Sympozium design is not used.
