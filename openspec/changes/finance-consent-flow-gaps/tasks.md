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
