# Tasks

## 1. Move the files

- [x] 1.1 Move `article_writer_system.md`, `article_structures.md`, `article_audiences.md` and
  `article_writer.md` (as `article_task.md`) from `agents/n8n/prompts/` to
  `agents/adapters/pi-writer/prompts/`.
- [x] 1.2 Inline the article AI-speak list into the adapter's `article_writer_system.md`; leave
  `agents/n8n/prompts/ai_speak.md` for the LinkedIn lane.
- [x] 1.3 Bake the prompt directory into the image with one `COPY prompts/` line.

## 2. Render in the adapter

- [x] 2.1 Add `fillTemplate` to `session-lib.mjs` and `articlePrompt` to `session-server.mjs`.
- [x] 2.2 Accept `brief` on the request and keep `messages` as the plain-text fallback.
- [x] 2.3 Replace the drafting prompt's research section, which named two tools the pod does not
  have, with `curl` as the sandbox map describes.

## 3. Send fields from n8n

- [x] 3.1 Add the optional `repo_path` input to `DownloadTemplate`.
- [x] 3.2 Rewrite `build_article_request` to post the `brief`, and remove the five drafting
  `DownloadTemplate` nodes from `Article Creator`.
- [x] 3.3 Point the review's `download_writer_rules` at the adapter's rules file, and the review and
  improvement fetches of the audiences and shapes at the adapter's directory.
- [x] 3.4 Remove the article lane's `download_ai_speak` fetches.

## 4. Record and verify

- [x] 4.1 Update `docs/agent/n8n.md`, `AGENTS.md` and the adapter README.
- [x] 4.2 Write the `content-writer` delta and archive the change.
- [x] 4.3 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` — 31 passed.
- [x] 4.4 `uv run -- pytest agents/n8n/scripts/ -q` — see the pull request body.
- [x] 4.5 `openspec validate --all` — see the pull request body.
- [ ] 4.6 Rebuild the `pi-writer` image, pin its digest, apply both graphs to the live instance and
  read them back: owner-side, `[UNVERIFIED]` from the Pod.
