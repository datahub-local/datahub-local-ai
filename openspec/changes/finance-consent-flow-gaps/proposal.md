# Proposal

## Why

The Enable Banking consent for the single finance account (`cuenta_compartida`, Openbank) has failed twice in one week, each time needing a manual token regeneration, and the daily check could not see it because the failure is an ASPSP-side error on `/accounts/{uid}/details` rather than an expired session. A line-by-line review of the reference's Account information flow found the renewal flow is incomplete: it skips `GET /aspsps`, discards the one-time account fields returned by `POST /sessions`, never closes the session it replaces, and ignores the redirect's `error`/`error_description`. The pipeline depends on `/details` for account metadata, which is exactly the endpoint that faults.

## What Changes

- Persist the one-time `POST /sessions` account fields (`identification_hash`, `currency`, `owner_name`) at onboarding and at renewal, and prefer them over `GET /accounts/{uid}/details` so the details endpoint becomes optional rather than load-bearing.
- Match authorised accounts to configured aliases by `identification_hash` first, falling back to IBAN.
- Call `GET /aspsps` in the renewal to resolve the ASPSP by its stored name, cap the requested validity at the ASPSP's `maximum_consent_validity`, assert the configured `psu_type` is supported, and fail loudly when the stored name no longer exists (rebrand).
- Close the superseded session (`DELETE /sessions/{id}`, best-effort) after a renewal stores the new one.
- Read `error`/`error_description` on the bank redirect and report the bank's real reason instead of a missing-code error.
- Record the flow and these decisions in `docs/specs/005-personal-finance-datalake.md`.

## Capabilities

### New Capabilities

- `finance-enablebanking-consent`: how the finance pipeline obtains, renews and tracks Enable Banking account-consent sessions, keeps account metadata usable when the details endpoint faults, and reports consent failures with the bank's reason.

### Modified Capabilities

_None — no OpenSpec capability exists yet; this change creates the first one._

## Impact

- `workflows/dlt/projects/finance/onboard.py`, `config.py`, `providers/enablebanking.py` and their tests under `workflows/dlt/tests/finance/`.
- `agents/n8n/workflows/enable_banking_token_renewal.workflow.json` — export edit plus a live apply through `scripts/apply_workflow_changes.py` (needs separate approval).
- Secret shape: `finance-enablebanking/tokens.json` gains optional per-account `identification_hash`, `currency`, `owner_name`; `finance-enablebanking/accounts.json` gains an optional `identification_hash`. Existing secrets keep working (fields optional, backfilled on the next renewal).
- Docs: `docs/specs/005-personal-finance-datalake.md`, `workflows/dlt/README.md`.
- No new dependencies; `GET /aspsps` and `GET /sessions/{id}` are meta calls that spend no PSD2 data budget.
