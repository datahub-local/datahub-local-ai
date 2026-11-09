# Spec Delta

## ADDED Requirements

### Requirement: One row's turn does not wait for another row's

The adapter SHALL serialise turns per session id and SHALL run turns of different sessions at the
same time. The source proxy SHALL admit only the hosts that every turn in flight declared, so
concurrency cannot widen an allowlist. A drafting turn SHALL finish and write its artifacts when
the caller's connection closes, and every other task SHALL still be cancelled by that close.

#### Scenario: Two rows are drafted at once

- **WHEN** two sessions each send a turn while the other is running
- **THEN** both turns run, and neither waits for the other to finish
- **AND** an unquoted block in one row's draft does not delay the other row

#### Scenario: One session's two turns

- **WHEN** two turns for the same session arrive together
- **THEN** they run one after the other, because they share one transcript file

#### Scenario: The caller's timeout closes the connection

- **WHEN** a drafting turn outlives the caller's deadline and the socket closes
- **THEN** the turn finishes and `article.md` and its ledger are written
- **AND** the next attempt for that row edits the artifact instead of drafting from nothing

#### Scenario: Two turns declare different hosts

- **WHEN** one turn declares a source host another does not
- **THEN** the proxy refuses that host for both while both are in flight

### Requirement: The audit runs in its own session

The `audit` task SHALL run in a session of its own, not the drafting session, so its prompt is the
article, the gate list and the prompts rather than the draft conversation. Its evidence SHALL
remain the drafting session's transcript, named in its prompt.

#### Scenario: A draft with a long transcript is audited

- **WHEN** the drafting session holds a large transcript
- **THEN** the audit's prompt carries the article and the gate list, not that transcript
- **AND** it is told the path of the transcript to search
