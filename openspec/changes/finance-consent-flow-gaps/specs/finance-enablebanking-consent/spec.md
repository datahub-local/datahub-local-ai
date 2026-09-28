# Spec Delta

## Purpose

Defines how the finance pipeline obtains, renews and tracks Enable Banking account-consent sessions, keeps account metadata usable when the per-account details endpoint faults, and reports consent failures with the bank's own reason.

## ADDED Requirements

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

### Requirement: A dead consent is detected on the data plane

The scheduled consent check SHALL probe a live data endpoint — `GET /accounts/{uid}/balances` — for every stored account, because Enable Banking documents that `GET /sessions/{id}` may report a session valid when a data fetch would fail. The check SHALL treat an authentication failure on that probe (`EXPIRED_SESSION`, an ASPSP auth error) as needing renewal and SHALL report the alias and the probe's error. It SHALL distinguish a rate-limit response (`429`/`RATE_LIMIT`) from a dead consent and SHALL NOT treat it as one. `GET /sessions/{id}` SHALL remain a secondary, budget-free signal reported alongside. Because the data probe spends one PSD2 data call per account, it SHALL run at most once per day.

#### Scenario: The data probe succeeds

- **WHEN** `GET /accounts/{uid}/balances` returns success for every stored account
- **THEN** the check reports no consent needing attention

#### Scenario: The data probe reports a dead session

- **WHEN** `GET /accounts/{uid}/balances` reports an expired session or an ASPSP auth failure for a stored account
- **THEN** the check reports that account as needing renewal, with the probe's error

#### Scenario: A session-status mismatch is not a false alarm

- **WHEN** `GET /sessions/{id}` is not `AUTHORIZED` but the data probe succeeds
- **THEN** the check does not demand a renewal and reports the session state only as context

#### Scenario: A rate limit is not a dead consent

- **WHEN** the data probe reports a rate limit rather than an authentication failure
- **THEN** the check does not mark the account as needing renewal

### Requirement: An hourly watch records consent-state transitions

A scheduled hourly check SHALL read each stored session's state from `GET /sessions/{id}` and SHALL post a Slack notice only when a session's observed state differs from the state recorded on the previous run, so that a change is timestamped once and an unchanged state stays silent. It SHALL persist the last observed state between runs.

#### Scenario: A state change is reported once

- **WHEN** a session's state changes from `AUTHORIZED` to any other value
- **THEN** the watch posts one Slack notice naming the session, account and new state

#### Scenario: An unchanged state is silent

- **WHEN** every session's state equals the state recorded on the previous run
- **THEN** the watch posts nothing

### Requirement: The renewal nudge links to the live form

The renewal link carried by the nudge SHALL reference the workflow's current form id, so that following it opens the renewal form.

#### Scenario: The nudge link resolves

- **WHEN** the check builds a nudge
- **THEN** the link's form id equals the renewal form trigger's id in the same workflow
