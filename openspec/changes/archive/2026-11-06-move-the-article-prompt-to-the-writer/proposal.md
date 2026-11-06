# Proposal

## Why

The article's drafting prompt was assembled in n8n: `Article Creator` fetched
`article_writer_system.md`, `article_writer.md`, `article_structures.md`,
`article_audiences.md` and `ai_speak.md`, rendered their placeholders with the entry's values, joined
the system and task halves, and posted the whole text to the `pi-writer` session as one user message.
The writer agent received a brief it could not inspect and a prompt it did not own.

That split put the words the model reads in one repository path and the adapter that runs them in
another. It also meant every prompt change was a graph-shaped change: a new placeholder had to be
added to the `DownloadTemplate` call before the text could use it, and the graph could not be checked
against the prompt it was sending.

## What Changes

- **`agents/adapters/pi-writer/prompts/`** becomes the home of the drafting prompt:
  `article_writer_system.md`, `article_task.md` (from `article_writer.md`), `article_structures.md`
  and `article_audiences.md`, baked into the image beside the existing `writing.md`.
- **The adapter renders the brief.** The request carries a `brief` object with the entry's fields —
  topic, description, link, budget, asset types, audience, extra rules, source text, feedback and the
  previous draft — and the server fills the task template from its own files. `messages` stays as a
  plain-text fallback for a caller that is not the article lane.
- **`Article Creator` sends the fields, not the prompt.** `build_article_request` posts the `brief`,
  the session id, the attempt and the source hosts; the five drafting `DownloadTemplate` nodes are
  removed from that graph.
- **The gate reads the same rules file.** `DownloadTemplate` gains an optional `repo_path`, so the
  review and the improvement pass fetch `article_writer_system.md` from the adapter's directory
  instead of keeping a second copy in `agents/n8n/prompts/`.
- **The article AI-speak list moves with the rules.** It is inlined into the adapter's
  `article_writer_system.md`; the LinkedIn lane keeps `agents/n8n/prompts/ai_speak.md`.

## Capabilities

`content-writer`.

## Out of scope

- The review, aspect and improvement prompts stay n8n LLM nodes; only the drafting prompt moves.
- No prompt wording change beyond the research section, which named two tools the pod does not have
  and now names `curl` as the sandbox map does.
