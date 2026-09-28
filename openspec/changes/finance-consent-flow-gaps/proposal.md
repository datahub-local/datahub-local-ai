# Proposal

## Why

The Enable Banking consent for the single finance account (`cuenta_compartida`, Openbank) has failed three times in one week (2026-09-24, 09-26, 09-28), each time needing a manual token regeneration. A line-by-line review of the reference's Account information flow found the renewal flow is incomplete: it skips `GET /aspsps`, discards the one-time account fields returned by `POST /sessions`, never closes the session it replaces, and ignores the redirect's `error`/`error_description`. The pipeline depends on `/details` for account metadata, which is exactly the endpoint that faults.

The 2026-09-28 investigation added two findings. First, the liveness signal is wrong: the daily check trusts `GET /sessions/{id}`, but Enable Banking documents that a session "may expire or expiration may be detected during the fetch of account information … even if the previous response indicated that the session was valid." Live on 09-28 the session read `AUTHORIZED` while `GET /accounts/{uid}/balances` and `/transactions` returned `EXPIRED_SESSION` and `/details` returned an ASPSP auth failure — so the check reported `Healthy, No Action` hours before the 06:00 ingest failed. Second, the nudge link is stale: `Evaluate Consent` points at the form id `7c1f51ab-…`, but the form's id changed to `0c19a176-…` in commit `8df0f1b`, so a nudge's renewal link no longer resolves.

## What Changes

- Persist the one-time `POST /sessions` account fields (`identification_hash`, `currency`, `owner_name`) at onboarding and at renewal, and prefer them over `GET /accounts/{uid}/details` so the details endpoint becomes optional rather than load-bearing.
- Match authorised accounts to configured aliases by `identification_hash` first, falling back to IBAN.
- Call `GET /aspsps` in the renewal to resolve the ASPSP by its stored name, cap the requested validity at the ASPSP's `maximum_consent_validity`, assert the configured `psu_type` is supported, and fail loudly when the stored name no longer exists (rebrand).
- Close the superseded session (`DELETE /sessions/{id}`, best-effort) after a renewal stores the new one.
- Read `error`/`error_description` on the bank redirect and report the bank's real reason instead of a missing-code error.
- Detect a dead consent on the **data plane**: the scheduled check probes `GET /accounts/{uid}/balances` for every stored account and treats `EXPIRED_SESSION`/`auth failure` as needing renewal, keeping `GET /sessions/{id}` only as a secondary (free) signal.
- Add a small hourly `EnableBanking Consent Watch` workflow that probes each stored session through `GET /sessions/{id}` (no PSD2 budget) and posts to Slack only when a session's state changes, timestamping the flip for the next failure.
- Fix the daily nudge's renewal link to the form's current id.
- Record the flow and these decisions in `docs/specs/005-personal-finance-datalake.md`.

## Capabilities

### New Capabilities

- `finance-enablebanking-consent`: how the finance pipeline obtains, renews and tracks Enable Banking account-consent sessions, keeps account metadata usable when the details endpoint faults, and reports consent failures with the bank's reason.

### Modified Capabilities

_None — no OpenSpec capability exists yet; this change creates the first one._

## Impact

- `workflows/dlt/projects/finance/onboard.py`, `config.py`, `providers/enablebanking.py` and their tests under `workflows/dlt/tests/finance/`.
- `agents/n8n/workflows/enable_banking_token_renewal.workflow.json` — export edit plus a live apply through `scripts/apply_workflow_changes.py` (needs separate approval).
- `agents/n8n/workflows/enable_banking_consent_watch.workflow.json` — new hourly workflow, created live with `--create` (needs separate approval).
- Secret shape: `finance-enablebanking/tokens.json` gains optional per-account `identification_hash`, `currency`, `owner_name`; `finance-enablebanking/accounts.json` gains an optional `identification_hash`. Existing secrets keep working (fields optional, backfilled on the next renewal).
- Docs: `docs/specs/005-personal-finance-datalake.md`, `workflows/dlt/README.md`.
- No new dependencies; `GET /aspsps` and `GET /sessions/{id}` are meta calls that spend no PSD2 data budget, which is why the hourly watch uses the session-status endpoint and the daily check carries the single data-plane probe.
