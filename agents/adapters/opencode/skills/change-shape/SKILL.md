---
name: change-shape
description: How a change in these repositories is shaped: when it needs an OpenSpec change, the commit format and scopes, what belongs in a comment, and the invariants that have broken before. Use before planning a multi-step change or committing.
---

# Change shape

## Does it need an OpenSpec change?

Create `openspec/changes/<kebab-id>/{proposal,design,tasks}.md` when the change is
a new capability, a behaviour change, or multi-step work. One-line fixes, a
version bump, a typo and a dependency update do not.

Check `openspec/specs/` before deciding there is none: a capability that already
has a spec and changes behaviour needs a delta, or the spec now describes the code
as it used to be. A fix, a version bump, a typo and a dependency update need
nothing, and the issue plus the pull request are the record for those.

A change is a decision record, not a plan: keep the alternatives that lost and
why, mark a task `[x]` as it lands rather than deleting it, and mark what you
could not verify `[UNVERIFIED]` in place.

Archive before the final commit, in the same branch:

```
openspec archive <id> --yes
```

It moves the directory to `changes/archive/<date>-<id>/` and applies the delta to
`specs/<capability>/spec.md`, so the pull request merges a spec that is already
true and no second pull request is needed to finish the job. The archived
proposal, design and delta stay in the diff, so the reviewer still sees the
decision. Archived, never deleted.

`openspec validate --all` is part of the gate.

## Commits

```
type(scope): subject
```

- `type`: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`.
- `scope`: the sub-project, named as its directory is. In `datahub-local-ai`:
  `dbt`, `dlt`, `airflow`, `n8n`, `sympozium`, `superset`, `opencode`,
  `semantic`. In `datahub-local-core`: the release, such as `sympozium`, `n8n`,
  `trino`, `monitoring`. Drop the scope for a repository-wide change.
- `subject`: imperative, lowercase, no trailing period, 50 to 70 characters.

No body by default. Rationale belongs next to the code, in the repository's
`AGENTS.md`, or in the OpenSpec change. A body is for a breaking change, a
required manual step, or a dependency on another repository.

One commit for one coherent change. Do not split a change by file type, and do
not bundle two unrelated fixes.

## Comments

- YAML and helmfile carry values, not prose. A comment beside a value is a second
  copy of a decision that drifts from it. The reasoning lives in the sub-project's
  `MEMORY.md`.
- Python and shell keep a comment for a non-obvious *why*: the trap, the reason,
  the invariant. Never what the line does, never history.
- Prompt text is a file. An instruction a model reads is declared in a prompt
  file, never inline in a node or a script.

## Invariants that have broken before

- A test ships with the behaviour change and fails without it. A wording change
  to a prompt or a rule file is not behaviour, and a unit test over that text is
  a second copy of the wording: it fails every legitimate rewrite.
- Nothing user-facing reads bronze. A consumer needs `silver` or `gold`.
- Superset object `uuid`s are the stable identity across re-imports. Never
  regenerate one.
- A prompt rule and the gate that enforces it live in two files and change
  together, or the loop is unsatisfiable.
- Deployment is two halves: the image commit, then the digest pin in
  `datahub-local-core`. Neither half alone changes the cluster.
