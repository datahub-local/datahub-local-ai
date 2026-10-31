# Design

## Context

Six scheduled reporters in `homelab-ops` post one report each to Slack. Delivery is
`deliveryMode: hook`: `files/deliver-slack.py` runs as a `postRun` container, converts the
run's Markdown to mrkdwn, writes the `"<Agent> | <ensemble> | <cadence>"` header, computes
the verdict emoji from the converted body and prefixes it to the `Status` line. The model
never writes an emoji.

`Verdict.classify` reads structure, not content: `ERROR:` anywhere is red, a section whose
label is in `FINDING_SECTIONS` and whose content is not one of its nothing-forms is a
warning, and everything else is green. `NOTHING` is anchored at the start of a bullet, so a
section's first bullet decides it only when it is the section's only bullet.

## Gate findings

Read from the repository and from the live `AgentRun` objects in `namespace automation` on
2026-10-31, not from memory.

- **The clean report that warned.** `homelab-ops-gitops-auditor-schedule-203`:
  `Status: All ten applications are Synced and Healthy; nothing needs action this run`.
  `_sections` gives `drift` = `- No drifting application: … | - Every row shows runs
  drifted as - … | - datahub-local-ai-superset, …` and `escalating` = `- Nothing growing:
  … | - Worth watching, not a finding: … | - facts_argocd_drift timed out on two attempts`.
  `_is_empty` sees non-nothing bullets in both. Re-running the committed classifier on that
  text returns `⚠️`, which is the symbol the user saw.
- **It is not one run.** Last eight stored runs per persona, classified with the committed
  hook: `gitops-auditor` 3/3 clean runs warned; `workload-watch` runs 56, 57, 59 and 60 said
  `Nothing needs action` or `all clear` and warned; `service-janitor` 62 and 63 said
  `recoverable` and warned. `db-steward`, `endpoint-warden` and `sre-sentinel` warned too,
  but every one of those carried a real finding (Prometheus fill, degraded amd-2, new
  alerts) and matches its `Status`.
- **`Idle` was misclassified by the code, not by the model.** `workload_watch_system.md`
  says "Idle is not broken and is never a finding on one reading", and `idle` was in
  `FINDING_SECTIONS`; the section's own purpose is to report a count, which can never be a
  nothing-form, so any run that reported it warned.
- **`Restarting` has no threshold, so it warns on noise.** Runs 56-57 and 59-60 carried one
  or two restarts across the fleet; run 61 carried 103 on `sympozium-mcp-firecrawl`. The
  prompt stated no line between them.
- **`endpoint-warden`'s `Maintenance` and `db-steward`'s `Room to grow` are readings by
  design**: "pending security updates, as the machines and the count" and "how many claims
  are at or above warn" both open with their subject, so their clean state (`0 pending`,
  `0 of 32`) does not match `NOTHING` and posts a warning. These stay finding sections —
  a pending security update and a claim at warn are actionable — and gain a stated empty
  form instead.
- **A rule the model could not satisfy.** `gitops_auditor_system.md` said "Never repeat a
  call"; the primary facts call timed out twice in run 203 and the retry is what produced
  the report. With no retry the run has no data at all, which the same prompt calls
  `unknown, not synced`.
- **Shipping** is a commit on `main`: `datahub-local-ai-sympozium` is an ArgoCD application
  over this repository at `agents/sympozium/`, `HEAD`, and no Helm release of that name
  exists. The measured effect of the previous prompt change is that the sync updates
  `agentConfigs[].systemPrompt` and the postRun script and fires no run, so the next
  scheduled tick is the first report under the new contract.

## Decisions

- **State the empty form in `hook.md`, not in the classifier.** The classifier is the one
  thing that must not depend on model judgement, so relaxing `NOTHING` to guess at prose
  would trade a visible false warning for an invisible missed finding. The prompt is where
  the model can read the rule; the code keeps the verdict.
- **`Idle` is clean; `Restarting` is a finding with a threshold.** The distinction is what
  the persona's own prompt already says: idle is never a finding, and a restart count is
  evidence until it is a loop. Moving `Restarting` to clean would have made a 103-restart
  loop post green, which is the failure the classifier exists to prevent.
- **The empty form may carry the reading after a colon.** `Nothing stale: newest successes
  5.0h ago, 0 recent failures` keeps the figure that proves it and still classifies clean;
  forbidding the reading would have deleted the evidence instead of the warning.
- **Commentary is banned by the same rule that names the form.** The model wrote
  `Worth watching, not a finding:` because the prompt asked "what is growing or
  persistent". Naming the forbidden shapes is what the 2026-10-30 measurement taught:
  forbid a shape and the model finds the next one.

## Risks

- **The empty form is a prompt rule with no runtime check.** A model can still add a second
  bullet to a clean section; the next run will warn and be read as a regression. The test
  holds the prompt, not the output, which is the same limit every report-shape test has.
- **`Restarting`'s threshold of 2 is a judgement**, chosen from the measured split (1-2
  across the fleet against 103 in the loop). It is stated in the prompt so a change is a
  prompt edit, not a code change.
- **`endpoint-warden` keeps warning every run** until the stale apt cache is decided; the
  emoji is right about the fleet and the fleet is the open question.

## Open questions

- Should a permanently stale apt cache be a finding at all, a lower-severity reading, or a
  standing exception listed in the persona's memory seeds? Not decided here.

## Definition of done

- `hook.md` carries the empty-form rule, and every finding section in every reporter format
  states its own empty form.
- `Idle` classifies clean and a 103-restart bullet still classifies as a warning.
- `uv run pytest agents/sympozium/tests/` and `helmfile template` pass in
  `agents/sympozium/`, and `openspec validate --all` passes.
- The next scheduled report of each persona carries an emoji that its `Status` line
  supports.
