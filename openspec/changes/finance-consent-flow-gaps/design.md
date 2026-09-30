# Design

## Context

See `proposal.md` - Why. The relevant current state:

- `agents/n8n/workflows/enable_banking_token_renewal.workflow.json` does the whole browser consent: form → `POST /auth` (name from `finance-enablebanking/accounts.json`, `country: ES`, `psu_type: personal`, `valid_until = now + 180 d`) → bank redirect → `POST /sessions` → upsert `finance-enablebanking-token`.
- `workflows/dlt/projects/finance/providers/enablebanking.py` reads the session `uid` from the token secret and calls `/details`, `/transactions`, `/balances`. `/details` was just made best-effort, so a failure there no longer aborts the run, but the fallback account has empty `currency`/`owner_name`.
- The two secrets are `finance-enablebanking` (operator-pasted: `private_key`, `accounts.json`) and `finance-enablebanking-token` (n8n-written: `tokens.json`). Only the token secret is writable by n8n.
- Live `GET /aspsps` for Openbank: `beta: true`, `maximum_consent_validity: 15552000` (180 d), `psu_types: [business, personal]`, `required_psu_headers: null`, unnamed `REDIRECT` auth methods.
- The daily check's only liveness signal is `GET /sessions/{id}`. On 2026-09-28 that read `AUTHORIZED` while every data call failed (`EXPIRED_SESSION`/ASPSP auth failure), and the check reported `Healthy, No Action` before the 06:00 ingest failed. Enable Banking's FAQ documents this gap explicitly.

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

**7. The daily check nudges; the watch decides liveness.** The daily check spends
no data-plane call: it nudges when a stored `valid_until` is ≤ 3 days out or
when the budget-free `GET /sessions/{id}` read is not `AUTHORIZED` (or fails).
It carried a `GET /accounts/{uid}/balances` probe from 2026-09-28, when the
session-status read proved inconclusive (it said `AUTHORIZED` while every data
call was dead), and gave it up on 2026-09-29 to the watch, because the probe was
one of the ~8 data fetches a day the fleet was spending against Openbank's ~4
background limit. A non-`AUTHORIZED` session read still earns a nudge — it is
never proof of life, but it is never *good* news either — and the wording says
the 12 h watch confirms on the data plane.

*Alternatives:* keep trusting `/sessions/{id}` alone — rejected, it produced a
false "healthy" on 09-28. *Keep the daily balances probe alongside the watch* —
rejected on 09-29, it is a duplicate of the watch's signal at a cost the budget
does not have. *Probe balances hourly* — rejected, it exceeds the limit and
returns `429`, not a better answer.

**8. The watch probes the data plane every 12 hours, not the session status
hourly.** `EnableBanking Consent Watch` calls `GET /accounts/{uid}/balances`
twice a day, posting to Slack when an account's state differs from the previous
run's, persisted in `$getWorkflowStaticData('global')` under a `consent_states`
key. Two reasons the probe is a data fetch: (a) Enable Banking performs the
ASPSP token renewal **during data fetches**, so a session-status read does
nothing to keep the connection alive; (b) the session-status read is not a
reliable signal anyway. The cadence is 12 h, not the 6 h the watch shipped with,
because the fleet's data-fetch budget is ~4/day per account on Openbank and the
honest count was ~8 (watch 4 + daily check 1 + ingest 3); at 12 h the fleet
lands at 4 (watch 2 + ingest 2, once `/details` is skipped per decision 10).
Consent drops have happened since the integration started — 2026-09-24, 09-26,
09-28 and 09-29 — under no watch, an hourly session-status watch and a 6-hourly
data-plane watch alike, so the cadence buys **detection, not prevention**, and
12 h is the detection window the budget allows. The `consent_states` key
deliberately does not read the earlier `session_states`, because the
vocabularies differ (`AUTHORIZED` vs `OK`) and comparing them would post a
spurious transition on the first tick. Two additions on 2026-09-29 close the
silence holes the 09-29 drop exposed: a non-OK state observed for the **first**
time (fresh static data, a new alias, or a consent already dead at deploy —
exactly what happened) is posted, because a transitions-only rule would silence
it forever; and `Build Probes` throws when accounts are configured but no
session uid is probeable, because a missing token Secret otherwise makes the
watch probe nothing and report "unchanged" forever. It duplicates the secret
read and JWT mint because n8n has no shared-code unit; the duplication is
bounded to those two nodes.

*Alternatives:* hourly — rejected, it blows the 4/day limit and returns `429`.
*6 h* — rejected on 09-29, it put the fleet at 6 fetches/day against a ~4 limit
for a detection window no drop has ever respected. *Fold the watch into the
renewal workflow* — rejected, two triggers feeding the same nodes makes the
branches inseparable. *Store state in a ConfigMap* — rejected, the n8n
ServiceAccount has no ConfigMap write and static data is enough.

**9. The nudge link.** The form id is a literal in `Evaluate Consent`; it is corrected to the current id and a scenario asserts it matches the form node, so the next rename fails a test instead of silently dead-ending the operator.

**10. `/details` is spent only until its answers are stored.** `list_accounts()`
skips `GET /accounts/{uid}/details` when the token secret already carries
`currency` and `owner_name` — the two account-row fields the call would add —
because they cannot change mid-session and every call spends one of the
ASPSP's ~4 background data fetches a day. A secret written before those fields
were captured still pays the call until the next renewal backfills them, and a
details fault keeps degrading to the configured fallback as before. The skipped
call leaves the account row's `payload_json` empty; nothing downstream reads it
(bronze is not a consumer layer).

*Alternative:* keep the call as a pure override — rejected on 09-29, it is a
daily data fetch for two values that are already stored.

**11. The watch's advice distinguishes a dead consent from an Enable Banking
fault.** The watch classifies each probe result the way the provider does:
`EXPIRED_SESSION`/revoked is the operator's to fix (re-link, form link
attached), a rejected credential points at the application, and
`ASPSP_ERROR`/other 4xx/5xx means Enable Banking or the bank is faulting —
retry. Transient faults share one bucket, so `ASPSP_ERROR` ↔ `500` churn posts
once rather than on every tick. Reason: on 2026-09-30 the balances call answered
`500 Internal server error` (and at 12:00 `400 ASPSP_ERROR`) while
`GET /sessions/{id}` answered `AUTHORIZED` with `valid_until` in 2027 — the
blanket "renew" advice was sending the operator to a bank login that could not
have helped, and because the stored state was the raw error name, two flavours
of the same upstream fault posted as two different states.

*Alternative:* keep one "not OK → renew" message — rejected, it spends a manual
SCA on an upstream fault, which is precisely the "renew every time we use it"
loop the operator reported.

## Risks / Trade-offs

- **Deleting a session still in use** → only delete ids present in the token secret before the overwrite and never the new id; treat deletion as best-effort.
- **A hash match against the wrong account** → the hash is bank-issued and immutable per account; when absent, IBAN is used, preserving today's behaviour.
- **`GET /aspsps` adds a failure point to the renewal** → it is the same endpoint the reference mandates first; a failure names the ASPSP and stops before the bank login, which is preferable to an authorisation that cannot succeed.
- **Existing token secret has no one-time fields** → fields are optional; the provider falls back to the current behaviour for one renewal cycle, and the next renewal backfills them.
- **The n8n export alone changes nothing** → the change is applied live with `apply_workflow_changes.py` and verified with a dry run, per the repo rule.
- **The data-fetch budget was miscounted, and is now designed.** The honest
  count on 2026-09-29 was ~8 fetches/day per account against Openbank's ~4
  background limit: watch 4 (6-hourly) + daily-check probe 1 + ingest 3
  (`/details` + `/transactions` + `/balances`); the design's earlier "6" counted
  only balances calls. Overshooting a limit that never answered with a `429`
  while sessions kept dying is one open explanation for the drops, so the
  package lands at 4: watch 2 (12-hourly) + ingest 2 (`/details` skipped per
  decision 10), daily check 0. If a `429` ever appears it is classified as a
  rate limit and never as a dead consent, so overshoot degrades to a missed
  alert rather than a false re-link.
- **Consent drops predate every mechanism built for them.** Measured drops on
  2026-09-24, 09-26, 09-28 and 09-29 happened with no watch, an hourly
  session-status watch and a 6-hourly data-plane watch alike, so no cadence
  prevents them and the keep-alive hypothesis has not earned its keep; the
  cause is ASPSP-side (Openbank is `beta: true` on Enable Banking; the FAQ lists
  single-session-per-PSU and pending KYC). The watch's value is detection, and
  its window is now 12 h — the price of the budget. A drop the ASPSP never
  reports still surfaces only when the ingest data call fails, which stays the
  backstop.
- **A transitions-only watch silences a consent that dies before its first
  tick.** Hit on 2026-09-29: the consent was already `EXPIRED_SESSION` on the
  watch's first run, so no transition ever existed to post and the drop was
  found by hand. Fixed by posting the first observation of a non-OK state; the
  residual risk is a one-post-per-reseed cost when static data is cleared,
  which is acceptable — a dead consent worth one Slack line.
- **The nudge link is a literal that can go stale again** → a test asserts it matches the form node's id.

## Migration Plan

1. Land the dlt changes; existing secrets load unchanged (new fields optional).
2. Edit the workflow export, dry-run the apply, then apply live with approval; the daily check keeps running throughout.
3. The next renewal backfills `identification_hash`/`currency`/`owner_name` into `tokens.json`.
4. Rollback is the previous export applied the same way; the token secret is unaffected by a workflow rollback.

## Open Questions

_None — the four gaps and their bounds are fixed; remaining choices are line-level._
