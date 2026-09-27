# Design

## Context

See `proposal.md` - Why. The relevant current state:

- `agents/n8n/workflows/enable_banking_token_renewal.workflow.json` does the whole browser consent: form → `POST /auth` (name from `finance-enablebanking/accounts.json`, `country: ES`, `psu_type: personal`, `valid_until = now + 180 d`) → bank redirect → `POST /sessions` → upsert `finance-enablebanking-token`.
- `workflows/dlt/projects/finance/providers/enablebanking.py` reads the session `uid` from the token secret and calls `/details`, `/transactions`, `/balances`. `/details` was just made best-effort, so a failure there no longer aborts the run, but the fallback account has empty `currency`/`owner_name`.
- The two secrets are `finance-enablebanking` (operator-pasted: `private_key`, `accounts.json`) and `finance-enablebanking-token` (n8n-written: `tokens.json`). Only the token secret is writable by n8n.
- Live `GET /aspsps` for Openbank: `beta: true`, `maximum_consent_validity: 15552000` (180 d), `psu_types: [business, personal]`, `required_psu_headers: null`, unnamed `REDIRECT` auth methods.

## Goals / Non-Goals

**Goals:**

- Make `GET /accounts/{uid}/details` optional by persisting the account fields that are only returned at session authorisation.
- Complete the reference flow in the renewal: resolve the ASPSP, cap validity, close the replaced session, and report the redirect's error reason.
- Keep the change backward-compatible with the existing secrets and the single-account, single-application fleet.

**Non-Goals:**

- PSU headers (Openbank requires none), `auth_method` selection (Openbank's methods are unnamed), payments, or the Actual sync.
- Matching accounts across a re-flag of `app_id`; the fleet has one application.
- Storing any field the ASPSP does not return; every new field is optional.

## Decisions

**1. Where the one-time fields live.** Persist them in **both** stores, because only the token secret is n8n-writable but it is session-scoped, while the IBAN-level identity is operator-owned:
- `finance-enablebanking/accounts.json` gains optional `identification_hash` (the stable cross-session key, written by `finance.onboard`).
- `finance-enablebanking/tokens.json` gains optional `identification_hash`, `currency`, `owner_name` (written by `finance.onboard` and by the renewal's `Build Token Upsert`), so a renewal captures the session-time values durably without operator action.
- The provider builds an account from `accounts.json` (alias, IBAN, app id, institution) enriched by `tokens.json` (hash, currency, owner), and uses the `/details` response only to override them when it succeeds.

*Alternatives:* accounts.json only — rejected, the renewal cannot write it, so a details fault right after a renewal still loses the fields. Token secret only — rejected, the stable identity (IBAN, app id, institution) belongs with the operator-owned secret.

**2. Matching authorised accounts to aliases.** `Build Token Upsert` matches by `identification_hash` when the configured account has one, else by IBAN, and fails naming an unmatched account. The FAQ calls the hash the reliable cross-session matcher; IBAN stays as the fallback for secrets not yet enriched.

**3. `GET /aspsps` in the renewal.** A new node between the form and `POST /auth` fetches `GET /aspsps?country=ES`, finds the entry matching the stored `institution_id`, and fails loudly if absent. It caps the requested `valid_until` at `maximum_consent_validity`, asserts `psu_type` is in `psu_types`, and includes `beta` in the renewed Slack notice. It is a meta call: no PSD2 budget.

*Alternative:* keep the hardcoded name/validity — rejected; the FAQ says a rebrand makes reconnect fail with the old name, and hardcoding 180 d silently breaks if an ASPSP lowers its maximum.

**4. Closing the replaced session.** After `Replace Token Secret`/`Create Token Secret` succeeds, the workflow reads the session id(s) captured *before* the overwrite and issues `DELETE /sessions/{id}` for each id different from the new one, signed with the owning account's `app_id`. Deletion is best-effort: a failure is logged and posted, never fatal, and the new session id is never a delete target.

*Alternative:* delete before creating the new session — rejected; a failed new consent would then leave no usable session.

**5. Redirect error handling.** `Code Present?` becomes a two-way check: a branch for `error`/`error_description` that builds the failure page from them, and the existing missing-code branch. No new node for the happy path.

**6. Session scoping of the token write.** `Build Token Upsert` keeps the whole `tokens` object and updates one alias at a time, so closing an old session cannot touch a session still in use by another alias.

## Risks / Trade-offs

- **Deleting a session still in use** → only delete ids present in the token secret before the overwrite and never the new id; treat deletion as best-effort.
- **A hash match against the wrong account** → the hash is bank-issued and immutable per account; when absent, IBAN is used, preserving today's behaviour.
- **`GET /aspsps` adds a failure point to the renewal** → it is the same endpoint the reference mandates first; a failure names the ASPSP and stops before the bank login, which is preferable to an authorisation that cannot succeed.
- **Existing token secret has no one-time fields** → fields are optional; the provider falls back to the current behaviour for one renewal cycle, and the next renewal backfills them.
- **The n8n export alone changes nothing** → the change is applied live with `apply_workflow_changes.py` and verified with a dry run, per the repo rule.

## Migration Plan

1. Land the dlt changes; existing secrets load unchanged (new fields optional).
2. Edit the workflow export, dry-run the apply, then apply live with approval; the daily check keeps running throughout.
3. The next renewal backfills `identification_hash`/`currency`/`owner_name` into `tokens.json`.
4. Rollback is the previous export applied the same way; the token secret is unaffected by a workflow rollback.

## Open Questions

_None — the four gaps and their bounds are fixed; remaining choices are line-level._
