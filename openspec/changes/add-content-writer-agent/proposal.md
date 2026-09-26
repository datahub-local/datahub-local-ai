# Proposal

## Why

The homelab already has an end-to-end, human-reviewed pipeline that turns a queued source into a published LinkedIn post with a generated image: `linked_in_post_sharing.workflow.json` reads `content_planner`, selects one article, drafts it, takes a Slack approval, generates and approves an image, then publishes. The personal blog (`alvsanand.com`) has no equivalent — the gap between "I have something to write about" and a published long-form article with a hero image is still manual. This change clones the proven n8n pattern for the blog instead of inventing a new runtime.

## What Changes

- Add a new `article_queue` page to the `content_planner` sheet, mirroring `content_queue`: rows authored outside this system carry a topic, a description, an optional source link, and a status.
- Add a new scheduled n8n workflow modeled on `linked_in_post_sharing`: read `article_queue`, select one `QUEUE` row, mark it `IN_PROGRESS`, retrieve the source content when a link is present, produce a long-form article draft, take a Slack approval, produce and separately approve one hero image, then publish.
- Add companion sub-workflows for the long-form article and its image, mirroring `LinkedIn Post Creator` and `LinkedIn Image Creator`, plus new prompt files under `agents/n8n/prompts/`.
- Review in Slack, as the LinkedIn flow does: a double approval (`sendAndWait`) for the article, and a separate double approval for the image. A rejection opens the existing retry form (Retry/Cancel plus free-text feedback) and regenerates only that artifact with the feedback; the other artifact's approval is preserved.
- Publish only when both are approved: commit the article and the image together in a single commit to the `alvsanand` repository's default branch (`docs/blog/posts/<YYYYMM>-<slug>.md` and the image under `docs/img/`), which GitHub Pages / `mkdocs gh-deploy` then serves. Direct to `main`, so this is the first n8n workflow that writes to a repository outside the homelab.
- Record the outcome in the `article_queue` row (status, article/image state, published URL, image path, commit reference).
- Add error handling per the repo rule: the entry-point workflow carries `settings.errorWorkflow`, and a companion error workflow marks the failed row and notifies Slack.
- **No Sympozium, no MCP server, no cluster change.** Everything is n8n, the Google Sheet and the GitHub API.

## Capabilities

### New Capabilities
- `content-writer`: a scheduled, Slack-reviewed n8n pipeline that turns an `article_queue` entry into a long-form blog article and one hero image, iterates each artifact on feedback, and commits both to the `alvsanand` repository once both are approved.

### Modified Capabilities
<!-- None. No spec exists yet under openspec/specs/. -->

## Impact

- **`agents/n8n/workflows/`**: new exports for the entry-point workflow, its error workflow, and the article + image sub-workflows. Per the repo rule these are backups; the change is only live once applied with `scripts/apply_workflow_changes.py`, and every workflow needs its failure path wired before it is done.
- **`agents/n8n/prompts/`**: new prompt files for the long-form article (system + task) and the article image, fetched at runtime through the existing `DownloadTemplate` workflow; they must follow the repo's AI prompt policy (short, literal, no copied data).
- **`content_planner` sheet**: new `article_queue` page and its columns. Rows are authored by a human.
- **GitHub**: a credential/token with `contents:write` scoped to `alvsanand/alvsanand`; whether the existing n8n GitHub credential already carries write scope is [UNVERIFIED].
- **`alvsanand`** (cross-repo): a push to `main` publishes through `.github/workflows/pages.yml`; post front-matter and image-path conventions must be respected.
- **No change** to `datahub-local-core`, `datahub-local-ai-mcp`, or Sympozium. The approved Sympozium design is not used.
