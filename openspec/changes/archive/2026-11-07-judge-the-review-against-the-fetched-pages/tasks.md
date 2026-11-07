# Tasks

## 1. The review prompt

- [x] 1.1 `prompts/article_review.md`: the fact check reads the entry's inputs, the seed page and
  every page the writer fetched during the run.
- [x] 1.2 The Source Material block says it is the seed page, and points at the session's
  earlier turns for the fetched pages.
- [x] 1.3 A fact from a fetched page is sourced even when the seed page does not carry it; a fact
  absent from all of them and a citation of an unfetched page remain failures.

## 2. Documentation

- [x] 2.1 `docs/agent/n8n.md`: the rule and execution 16033.

## 3. Gate

- [x] 3.1 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'`.
- [x] 3.2 `openspec validate --all`.

## 4. Deployment and recovery

- [ ] 4.1 Rebuild and pin the pi-writer image on merge; ArgoCD rolls the session.
- [ ] 4.2 Requeue row 3 once the new image is live and run it. [UNVERIFIED] until then.
