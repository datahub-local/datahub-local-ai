# Tasks

## 1. Persist one-time session data (dlt)

- [x] 1.1 Add optional `identification_hash` to `AccountConfig` and optional `identification_hash`, `currency`, `owner_name` to `TokenConfig` in `providers/enablebanking.py`; run `uv run pytest tests/finance/test_enablebanking.py` and confirm the existing suite still passes
- [x] 1.2 Parse the new optional fields in `config.enablebanking_accounts()` and `config.enablebanking_tokens()` with a test in `tests/finance/test_config.py` covering present and absent values
- [x] 1.3 Emit `identification_hash` in `finance.onboard`'s `accounts.json` fragment and `identification_hash`/`currency`/`owner_name` in its `tokens.json` fragment; update `tests/finance/test_onboard.py` and confirm it passes

## 2. Account metadata without `/details` (dlt)

- [x] 2.1 Make `_normalise_account`/`_configured_account` enrich the fallback account from the configured `AccountConfig`/`TokenConfig` (IBAN, currency, owner name; `XXX` treated as unknown) and treat the `/details` response as an override; extend `tests/finance/test_enablebanking.py::TestListAccounts` so a details failure still yields a populated account
- [x] 2.2 Confirm a data-call failure still fails loudly by running the existing `tests/finance/test_ingest.py` (rate-limit and missing-token cases) unchanged
- [x] 2.3 Run `uv run pytest` (158 passed) and `uv run ruff check` on the changed files (clean); note the repo baseline in `workflows/dlt` already carries 55 pre-existing lint errors unrelated to this change and CI does not lint it

## 3. Complete the renewal flow (n8n)

- [x] 3.1 Add a Code node after `List Accounts` that calls `GET /aspsps?country=ES` (via a preceding HTTP node), resolves the stored `institution_id`, caps the requested `valid_until` at `maximum_consent_validity`, asserts `psu_type` is in `psu_types`, and throws naming the ASPSP when it is absent; verify by rendering the export and checking the node/edge shape with the export tests
- [x] 3.2 Extend `Build Consent Request` to use the resolved name/country and capped validity from 3.1; verify the export tests pass and the node references the new node
- [x] 3.3 Extend `Build Token Upsert` to match session accounts by `identification_hash` first then IBAN, and to store `identification_hash`/`currency`/`owner_name` per alias; verify the export tests pass
- [x] 3.4 Add a best-effort `DELETE /sessions/{old_id}` step after the token upsert, for each session id no alias still references (so a shared session is kept) and signed with the owning account's `app_id`; a failure is non-fatal (`neverError`); verify the export tests pass
- [x] 3.5 Make the redirect branch read `error`/`error_description` and report the bank's reason, keeping the missing-code branch for the no-code/no-error case; verified by the export tests
- [x] 3.6 Dry-run the live apply with `scripts/apply_workflow_changes.py --changes ... ` (no `--apply`), confirm the field plan and require-edges, then apply with explicit approval and re-run the dry run to confirm `nothing to change`

## 4. Documentation

- [x] 4.1 Update `docs/specs/005-personal-finance-datalake.md` §4.1/§4.2.1 with the persisted one-time fields, the `GET /aspsps` step, the hash-first matching, and the session close; verify the sibling links still resolve
- [x] 4.2 Update `workflows/dlt/README.md` (link/re-link and renewal sections) to describe the new fragment fields and the session-close behaviour
- [x] 4.3 Correct the spec's Openbank `beta` note to match the live `GET /aspsps` (`beta: true`)

## 5. End-to-end verification

- [x] 5.1 Run the full `workflows/dlt` suite (`uv run pytest`), `uv run ruff check` on the changed files, and `uv run pytest agents/n8n/scripts/` for the export tests; confirm all green
- [x] 5.2 Trigger one manual renewal against the live workflow with approval and confirm the token secret gains the one-time fields, the superseded session is deleted, and the browser lands on the success page (operator: the bank login is the one manual PSD2 step)

## 6. Detect a dead consent (n8n)

- [x] 6.1 Fix the stale form id in `Evaluate Consent`'s nudge link to the live form id, and add an export test asserting the link's form id equals the `Form: Start Renewal` node id
- [x] 6.2 Make the daily check probe `GET /accounts/{uid}/balances` per stored account (add `Mint Probe JWT`/`Probe Account Data`, rework `Evaluate Consent`): classify `EXPIRED_SESSION`/ASPSP auth failure as needing renewal, treat `429`/`RATE_LIMIT` as non-renewal, and keep `GET /sessions/{id}` as a secondary signal
- [x] 6.3 Add `agents/n8n/workflows/enable_banking_consent_watch.workflow.json`: hourly schedule, secret read, `GET /sessions/{id}` per stored session, `$getWorkflowStaticData` transition detection, Slack only on change, `settings.errorWorkflow` set
- [x] 6.4 Run `uv run --project workflows/dlt pytest agents/n8n/scripts/` and confirm the export tests pass
- [x] 6.5 Dry-run then apply the renewal changes live (with approval), re-run to confirm `nothing to change`, and create the watch workflow live with `--create` (with approval)

## 7. Documentation

- [x] 7.1 Update `docs/specs/005-personal-finance-datalake.md` §4.2.1: replace the session-status-only probe with the data-plane probe, the `429` distinction, and the hourly watch; record the 2026-09-28 incident and the ASPSP-side root cause
- [x] 7.2 Update `workflows/dlt/README.md` with the data-plane detection and the watch

## 8. Keep-alive data fetch (n8n)

- [x] 8.1 Change `EnableBanking Consent Watch` from hourly `GET /sessions/{id}` to every 6 h `GET /accounts/{uid}/balances`, renaming `Hourly Watch` → `Six-Hourly Watch` and `Get Session Status` → `Probe Balances`, with state keyed on a new `consent_states` key (the old `session_states` vocabulary differs and would post a spurious transition)
- [x] 8.2 Update the export test: cron `0 */6 * * *`, `/balances` probe present, no session-status node, static-data transition detection still asserted
- [x] 8.3 Update the spec delta (requirement, design decision 8, risks), `docs/specs/005` §4.2.1 and `workflows/dlt/README.md`
- [x] 8.4 Dry-run then apply the rename and re-wire live (with approval), re-run to confirm `nothing to change`

## 9. Data-fetch budget and the watch's silence holes (dlt + n8n)

- [x] 9.1 Skip `GET /accounts/{uid}/details` in `providers/enablebanking.py` when the token secret carries `currency` and `owner_name`; test asserts no request is made and the row comes from the stored values
- [x] 9.2 Remove `Probe Account Data` from `enable_banking_token_renewal.workflow.json`, wire `Get Session Status` straight into `Evaluate Consent`, and nudge on a non-`AUTHORIZED` session read instead of a balances probe; update the node comments
- [x] 9.3 Change `EnableBanking Consent Watch` from `0 */6 * * *` to `0 */12 * * *` (rename `Six-Hourly Watch` → `Twelve-Hourly Watch`), post the first observation of a non-OK state, and throw when accounts are configured but no uid is probeable
- [x] 9.4 Invert and extend the export tests: the daily check spends zero data-plane calls; the watch is 12-hourly and carries both silence-hole guards
- [x] 9.5 Update `docs/specs/005` §4.2.1, `workflows/dlt/README.md`, and this change's design (decisions 7, 8, 10 and risks) and spec delta; record that consent drops have happened since the integration started, at every cadence tried
- [x] 9.6 Run the `workflows/dlt` finance suite, the export tests and ruff on the changed files
- [x] 9.7 Dry-run then apply both workflow changes live with `apply_workflow_changes.py --changes` (with approval), re-run to confirm `nothing to change` (applied 2026-09-30 06:45 CEST; live read-back matches the exports: watch 9 nodes / 12-hourly, renewal 40 nodes without `Probe Account Data`; both `active: true`)

## 10. The watch's advice distinguishes a dead consent from an EB fault (n8n)

- [x] 10.1 Record the 2026-09-30 finding: `GET /accounts/{uid}/balances` answered `500 Internal server error` (and at 12:00 `400 ASPSP_ERROR`) while `GET /sessions/{id}` answered `AUTHORIZED` with `valid_until` in 2027 and the renewal at 12:02 had succeeded
- [x] 10.2 Classify the watch's states as the provider does (`EXPIRED`/`AUTH`/`BANK_FAULT`/`RATE_LIMIT`), post advice per state, attach the renewal link only for `EXPIRED`, and bucket transient faults so `ASPSP_ERROR` ↔ `500` churn posts once
- [x] 10.3 Extend the export test: a bank fault must not be reported as a reason to re-link
- [x] 10.4 Update `docs/specs/005` §4.1/§4.2.1, `workflows/dlt/README.md` (runbook step 4) and this change's design decision 11 and spec delta
- [x] 10.5 Dry-run then apply the watch export live and read it back against the export (applied 2026-09-30 17:39 UTC, `versionId 9236438c-0b49-4d6b-b5d9-553b77e5206e`; live `Watch Transitions` jsCode equals the export, 9 nodes, `active: true`, `triggerCount: 1`; re-run prints `nothing to change`)
- [x] 10.6 Diagnose the day's pipeline failure as EB-side, not consent: the 13:00 UTC `job-dlt-ingest-finance-*` died with `ProviderError: Enable Banking returned 500 (Internal server error)` on `fetch_transactions`, `/details` already skipped, while `GET /sessions/{id}` answered `AUTHORIZED`; EB ticket to raise with the `x-request-id`s
- [x] 10.7 Correct 10.2 on the 17:42–17:44 evidence: the 12:02 session answered `500` to every data call **and** to `DELETE` for 5 h 40 min while `GET /sessions/{id}` reported `AUTHORIZED`, and a new consent at 17:42 cleared it (the 17:44 ingest loaded 111 transactions while the old session's `DELETE` still `500`ed) — so a bank fault reads "retry, and re-link if it persists", with the renewal link attached, not "retry, never re-link"
- [x] 10.8 Dry-run then apply the corrected advice live and read it back (applied 2026-09-30 17:48 UTC, `versionId 217dbef5-9c9c-4d64-aea7-014bba1bd40f`; live jsCode equals the export and carries "retry, and if it persists re-link")
