# Spec Delta

## ADDED Requirements

### Requirement: A session can be continued across turns

The authoring runtime SHALL treat a session identifier as durable state: a turn that
reuses an identifier SHALL resume the agent transcript and the working directory an
earlier turn created, and a turn that omits one SHALL create isolated state of its own.
The runtime SHALL serialize turns that share an identifier.

#### Scenario: A second turn resumes the session

- **WHEN** two turns are sent with the same session identifier
- **THEN** the second turn runs in the directory the first created
- **AND** the agent's transcript carries the first turn's context

#### Scenario: An unnamed session does not collide

- **WHEN** a turn is sent with no session identifier, or with a fresh one
- **THEN** it neither reads nor overwrites another session's state

### Requirement: A continuation edits the composition in place

When a session's directory already holds a composition, the instruction the runtime
delivers for that turn SHALL name that composition and ask for the request to be
applied to it in place and re-rendered, rather than to author a new one, so the work
already produced is kept and only what the request names changes.

#### Scenario: An edit turn keeps the composition

- **WHEN** a session with an existing composition is turned again
- **THEN** the turn's instruction names the existing composition and asks for the request to be applied to it
- **AND** the rendered artifact is regenerated from the edited composition

#### Scenario: A turn on an empty session authors

- **WHEN** a session identifier resolves to no existing composition — a first turn, or a reclaimed session
- **THEN** the turn authors a composition
- **AND** it does not fail for the missing file

### Requirement: Session state expires

The runtime SHALL reclaim a session's working directory and its agent transcript once
they are older than a configured retention window, without removing the session in
flight, so abandoned work cannot exhaust the workspace indefinitely. Reclaiming SHALL
be best-effort and SHALL NOT fail a turn. A turn that arrives for a reclaimed session
SHALL author a composition rather than fail.

#### Scenario: Expired state is reclaimed

- **WHEN** a session's state is older than the retention window
- **THEN** its directory and its transcript are removed

#### Scenario: Active and recent sessions are kept

- **WHEN** a session is in flight, or its state is within the retention window
- **THEN** it is not removed

#### Scenario: A reclaimed session degrades

- **WHEN** a turn arrives for a session whose state was reclaimed
- **THEN** it authors a composition rather than failing
