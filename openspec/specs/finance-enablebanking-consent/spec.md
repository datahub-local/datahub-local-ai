# finance-enablebanking-consent Specification

## Purpose
Defines how the finance pipeline obtains, renews and tracks Enable Banking account-consent sessions, keeps account metadata usable when the per-account details endpoint faults, and reports consent failures with the bank's own reason.

## Requirements

### Requirement: The consent flow resolves the ASPSP before authorising

The renewal and onboarding flows SHALL resolve the target ASPSP from `GET /aspsps` using the name and country stored for the account, and SHALL request a consent validity no longer than that ASPSP's declared `maximum_consent_validity`. The configured PSU type SHALL be one the ASPSP declares supported. When the stored ASPSP name is absent from the response, the flow SHALL fail naming the stored name rather than start authorisation against a name the bank no longer recognises.

#### Scenario: Stored ASPSP is resolved

- **WHEN** the stored account names an ASPSP present in `GET /aspsps`
- **THEN** the flow proceeds to authorisation with that ASPSP's name and country

#### Scenario: Requested validity is capped

- **WHEN** the requested consent validity exceeds the ASPSP's `maximum_consent_validity`
- **THEN** the requested validity is reduced to the ASPSP's maximum

#### Scenario: ASPSP name no longer exists

- **WHEN** the stored ASPSP name is not returned by `GET /aspsps`
- **THEN** the flow fails with a message naming the stored name and does not call `POST /auth`

### Requirement: One-time session account data is persisted

When a session is authorised, the flow SHALL persist the per-account fields that `POST /sessions` returns and later calls do not — at least `identification_hash`, `currency` and `owner_name` — keyed by the account alias. Authorised accounts SHALL be matched to configured aliases by `identification_hash` when both sides carry one, and by IBAN otherwise. An authorised account that matches no configured alias SHALL fail naming the account rather than be dropped.

#### Scenario: Session data is stored for every authorised account

- **WHEN** a session is authorised for a configured account
- **THEN** that account's `identification_hash`, `currency` and `owner_name` are stored keyed by its alias

#### Scenario: Matching prefers the identification hash

- **WHEN** a session account carries an `identification_hash` that matches a configured account
- **THEN** the account is matched to that alias even if the IBANs differ

#### Scenario: Matching falls back to IBAN

- **WHEN** neither the session account nor the configured account carries an `identification_hash`
- **THEN** the account is matched by IBAN

#### Scenario: Unknown authorised account

- **WHEN** a session authorises an account that matches no configured alias
- **THEN** the flow fails naming that account

### Requirement: Account metadata survives a details-endpoint failure

Loading an account SHALL NOT depend on `GET /accounts/{uid}/details`. When that call fails or is skipped, the account SHALL still be produced from the configured and persisted metadata — alias, IBAN, currency and owner name — and the account's transactions and balances SHALL still be attempted. Failures on those data calls (expired session, rate limit, rejected credential) SHALL still fail loudly.

#### Scenario: Details failure yields an account

- **WHEN** `GET /accounts/{uid}/details` fails for an account with persisted metadata
- **THEN** that account is produced with its configured IBAN, currency and owner name, and its transactions and balances are still fetched

#### Scenario: A dead session is still loud

- **WHEN** the transactions or balances call reports an expired session
- **THEN** the run fails naming the account and the renewal path

### Requirement: The superseded session is closed on renewal

After a renewal authorises and stores a new session, the flow SHALL delete each previously stored session id that the new session replaces. It SHALL NOT delete the newly stored session id. A failed deletion SHALL NOT fail the renewal.

#### Scenario: Old session is deleted

- **WHEN** a renewal stores a new session that replaces a stored one
- **THEN** the replaced session id is deleted

#### Scenario: New session is kept

- **WHEN** the renewal deletes superseded sessions
- **THEN** the newly stored session id is not deleted

#### Scenario: Deletion failure is not fatal

- **WHEN** deleting a superseded session fails
- **THEN** the renewal still reports success with the new session stored

#### Scenario: The superseded session was already dead

- **WHEN** the superseded session has already expired at Enable Banking
- **THEN** the delete reports `EXPIRED_SESSION` instead of `CLOSED`, so that session stays `EXPIRED`, and the renewal still succeeds

### Requirement: A failed consent is reported with the bank's reason

The redirect handler SHALL read the `error` and `error_description` query parameters, and a redirect carrying `error` SHALL be reported with that reason rather than as a missing authorisation code.

#### Scenario: Cancelled consent names the reason

- **WHEN** the bank redirects with `error=access_denied`
- **THEN** the failure reports the cancellation and its description

#### Scenario: Missing code without an error

- **WHEN** the redirect carries neither `code` nor `error`
- **THEN** the failure reports a missing authorisation code

### Requirement: The daily check nudges without spending a data-plane call

The scheduled consent check SHALL NOT call a live data endpoint. It SHALL nudge
when a stored `valid_until` is within 3 days, and when the budget-free
`GET /sessions/{id}` read for a stored account is not `AUTHORIZED` or fails
outright, reporting the alias and the read's result. A session read that is not
`AUTHORIZED` SHALL be reported as needing confirmation on the data plane, never
as proof of a dead consent by itself, because Enable Banking documents that
`GET /sessions/{id}` may report a session valid while a data fetch fails. The
data-plane liveness probe belongs to the consent watch, not to this check.

#### Scenario: Expiry close nudges

- **WHEN** a stored account's `valid_until` is within 3 days
- **THEN** the check nudges naming the account and the expiry date

#### Scenario: A session read that is not AUTHORIZED nudges

- **WHEN** `GET /sessions/{id}` for a stored account returns a status other than `AUTHORIZED`, or the read fails
- **THEN** the check nudges naming the account and the read's result, and says the watch confirms on the data plane

#### Scenario: An AUTHORIZED session read is silent

- **WHEN** every stored account's session read returns `AUTHORIZED` and no expiry is close
- **THEN** the check reports no consent needing attention and spends no data-plane call

### Requirement: A dead consent is detected on the data plane

The consent watch SHALL probe a live data endpoint — `GET /accounts/{uid}/balances` — for every stored account, because Enable Banking documents that `GET /sessions/{id}` may report a session valid when a data fetch would fail. The watch SHALL treat an authentication failure on that probe (`EXPIRED_SESSION`, an ASPSP auth error) as a dead consent and SHALL report the alias and the probe's error. It SHALL distinguish a rate-limit response (`429`/`RATE_LIMIT`) from a dead consent and SHALL NOT treat it as one. Because each probe spends one ASPSP background data fetch, the watch SHALL run no more often than every 12 hours, keeping the fleet (watch plus ingest) inside the ASPSP's ~4/day background limit.

#### Scenario: The data probe succeeds

- **WHEN** `GET /accounts/{uid}/balances` returns success for every stored account
- **THEN** the watch records the state and reports no consent needing attention

#### Scenario: The data probe reports a dead session

- **WHEN** `GET /accounts/{uid}/balances` reports an expired session or an ASPSP auth failure for a stored account
- **THEN** the watch records that account as dead and reports it per the state-reporting rule below

#### Scenario: A rate limit is not a dead consent

- **WHEN** the data probe reports a rate limit rather than an authentication failure
- **THEN** the watch records the rate limit and does not report a consent change

### Requirement: A scheduled data fetch renews the token and records consent state

A scheduled check SHALL run every 12 hours and SHALL read a live data endpoint — `GET /accounts/{uid}/balances` — for every stored account, because a data fetch is what causes Enable Banking to renew the ASPSP access token internally, and because the data plane is the only reliable liveness signal. Twelve hours is the cadence because the ASPSP background limit is about 4 data fetches a day per account and the fleet's ingest spends two of them; consent drops have occurred since the integration started at every cadence tried, so the watch buys detection, not prevention. The check SHALL post a Slack notice when an account's observed state differs from the state recorded on the previous run, and also when a non-OK state is observed for an account with no recorded state, so that a consent already dead at the watch's first observation is reported instead of silenced forever. It SHALL persist the last observed state between runs, and it SHALL NOT post for a rate-limit response alone. It SHALL fail loudly when accounts are configured but no session is probeable, rather than report an unchanged state. It SHALL classify the observed state the way the provider classifies the same response, so that an expired or revoked consent is reported as needing a renewal, and an `ASPSP_ERROR` or a 5xx is reported as a bank fault to retry and to re-link if it persists — because a session can fail every call while `GET /sessions/{id}` reports `AUTHORIZED`.

#### Scenario: Each tick is a data fetch

- **WHEN** the schedule ticks
- **THEN** one balances call is made per stored account, twice a day

#### Scenario: A state change is reported once

- **WHEN** an account's data call moves from `OK` to `EXPIRED_SESSION`
- **THEN** the watch posts one Slack notice naming the account and both states

#### Scenario: A first observation of a dead consent is reported

- **WHEN** an account has no recorded state and its data call reports anything other than success
- **THEN** the watch posts one Slack notice naming the account and the observed state

#### Scenario: An unchanged state is silent

- **WHEN** every account's state equals the state recorded on the previous run
- **THEN** the watch posts nothing

#### Scenario: A rate limit is not a consent change

- **WHEN** the data call reports a rate limit rather than an authentication failure
- **THEN** the watch does not post

#### Scenario: A bank-side fault is reported as a retry that may need a re-link

- **WHEN** a data probe fails with an `ASPSP_ERROR` or a 5xx
- **THEN** the watch reports the bank fault, says to retry, and says to re-link if it persists, because a session can fail every call this way while `GET /sessions/{id}` reports `AUTHORIZED`

#### Scenario: Two flavours of the same fault post once

- **WHEN** a `400 ASPSP_ERROR` becomes a `500` with no successful call in between
- **THEN** the watch records the change without posting a second notice, because both are the same bank-fault state

#### Scenario: Nothing probeable fails loudly

- **WHEN** accounts are configured but no stored session uid exists to probe
- **THEN** the watch execution fails naming the missing token material instead of reporting an unchanged state

### Requirement: The renewal nudge links to the live form

The renewal link carried by the nudge SHALL reference the workflow's current form id, so that following it opens the renewal form.

#### Scenario: The nudge link resolves

- **WHEN** the check builds a nudge
- **THEN** the link's form id equals the renewal form trigger's id in the same workflow
