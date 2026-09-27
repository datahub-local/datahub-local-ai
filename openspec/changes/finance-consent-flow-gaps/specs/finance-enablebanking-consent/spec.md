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

### Requirement: A failed consent is reported with the bank's reason

The redirect handler SHALL read the `error` and `error_description` query parameters, and a redirect carrying `error` SHALL be reported with that reason rather than as a missing authorisation code.

#### Scenario: Cancelled consent names the reason

- **WHEN** the bank redirects with `error=access_denied`
- **THEN** the failure reports the cancellation and its description

#### Scenario: Missing code without an error

- **WHEN** the redirect carries neither `code` nor `error`
- **THEN** the failure reports a missing authorisation code

### Requirement: Every stored session is probed for liveness

The scheduled consent check SHALL probe `GET /sessions/{session_id}` for every distinct session id stored across accounts, signing each probe with the application id that owns that session, and SHALL report any session not in `AUTHORIZED` state together with its alias and superseded-expiry signal. A session that the ASPSP invalidates without Enable Banking reporting it is surfaced only by the ingest data call, which SHALL remain the backstop.

#### Scenario: One dead session among several

- **WHEN** two accounts are stored under two sessions and one is not `AUTHORIZED`
- **THEN** the check reports the failing session and its alias

#### Scenario: All sessions healthy

- **WHEN** every stored session reports `AUTHORIZED`
- **THEN** the check reports no consent needing attention
