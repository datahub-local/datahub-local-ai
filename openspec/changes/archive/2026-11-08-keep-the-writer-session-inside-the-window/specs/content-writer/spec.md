# Spec Delta

## ADDED Requirements

### Requirement: A writer session is compacted well inside the model window

The writer SHALL write Pi's `compaction` settings rather than leave them to the vendor default: it
SHALL keep compaction enabled, SHALL trigger it at a token count that leaves room for the
summariser's own request inside the context window, and SHALL derive its reserve from the context
window so a deployment that changes the window keeps the same trigger. It SHALL refuse a trigger
that is not inside the window and SHALL log the trigger with the window at boot.

#### Scenario: A session that has grown across retries

- **WHEN** a resumed session is larger than the trigger
- **THEN** Pi compacts it before the next request
- **AND** the request the gateway receives is the summary plus the recent tokens, not the whole history

#### Scenario: A trigger outside the window

- **WHEN** the configured trigger is zero or not below the context window
- **THEN** the server refuses to write the settings file
- **AND** the pod does not start on a configuration that cannot compact

#### Scenario: Evidence of the bound

- **WHEN** the session server starts
- **THEN** it logs the trigger and the context window it must fit inside
