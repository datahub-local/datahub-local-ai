# Design

## Decision: the adapter renders, the caller sends fields

The writer is the only component that knows what its prompt says, so it renders it. The request
carries a `brief` of entry fields and the adapter fills `article_task.md` from
`article_writer_system.md`, `article_structures.md` and `article_audiences.md`, all baked into the
image. A field the caller omits renders empty rather than leaving a `{{ NAME }}` the model would read
as a placeholder to fill; an unknown placeholder is left visible because it is a prompt bug.

Rejected: n8n sends the joined prompt (the status quo). It makes every prompt edit a graph edit, and
the agent cannot tell which words it was given from which words the caller assembled.

Rejected: n8n sends one rendered `messages` string built from the adapter's files over HTTP. It
adds a fetch and a failure mode to every turn for a text the adapter could just read.

## Decision: `repo_path` on `DownloadTemplate`, not a second copy for the gate

`article_review.md` and `article_improver.md` are n8n nodes and stay. They need the writer's rules.
`DownloadTemplate` already reads any path under the backup repo; an optional `repo_path` input lets a
caller name `agents/adapters/pi-writer/prompts`, with the `agents/n8n` default unchanged for every
other caller. So the review reads the committed file the adapter renders, and there is still one copy.

Rejected: keep `article_writer_system.md` in `agents/n8n/prompts/` for the gate and copy it into the
image at build. The two copies drift, and the 2026-09-30 failure was exactly a gate enforcing a list
the drafter was not reading.

Rejected: serve the file from a `/prompts/<name>` route on the session. The review would depend on
the writer pod being up and reachable, for a file GitHub already serves.

## Decision: `messages` stays as a plain-text fallback

The session contract is OpenAI chat shape, and the adapter's own smoke checks and the proxy tests
send `messages`. `brief` is the article lane's shape; a request without it keeps the old behaviour.
Removing `messages` would widen the change for no behaviour the issue asks for.

## Decision: the article's AI-speak list is inlined

The adapter cannot fetch `agents/n8n/prompts/ai_speak.md` at run time without a network dependency
and a prompt that is no longer reviewable with the image. The article list is inlined into
`article_writer_system.md`; the LinkedIn lane keeps its own file. Each lane owns its list, and the
gate reads the writer's copy through `RULES`.

## Verification

The adapter test `a brief is rendered from the adapter's own prompt files` proves each field reaches
the prompt and that the shapes and audience levels come from the image, not the request. The
existing proxy, artifact and correction tests still run through `messages`. Prompt wording itself is
not tested (`testing`): a test over the text fails every legitimate rewrite.

Live proof is the next drafting run after the image digest is pinned and the graph applied:
`[UNVERIFIED]` until then.
