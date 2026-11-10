# Spec Delta

## ADDED Requirements

### Requirement: An article is drafted from sources it has read

The drafting pass SHALL be a session turn with a working directory and read/fetch tools, not a single
prompt carrying one fetched page. The session SHALL be given the entry, the audience and the rules,
SHALL fetch the project's own documentation and repository files over HTTPS, and SHALL write two
artifacts: the article and a source ledger naming, for every fenced line, the URL it was read from.

#### Scenario: A row whose link is a brief

- **WHEN** the entry's link carries a brief but no commands, chart or version
- **THEN** the session reads the project's documentation and repository files before drafting
- **AND** the draft quotes the commands it found, each ledgered with its URL

#### Scenario: A source cannot be read

- **WHEN** no fetched page carries a command for a section
- **THEN** that section fences nothing and says in one sentence that the source could not be read
- **AND** no placeholder stands in for a command

### Requirement: Fenced lines are verified against a ledger the model does not own

Every fenced line in an article SHALL appear in the source ledger. The session server, not the model,
SHALL fetch each ledgered URL after the turn and drop the entries that do not answer; the drafting
gate and the improvement re-check MUST reject a fenced line that is absent from the ledger or whose
ledger entry was dropped, naming the line and the URL.

#### Scenario: An invented command

- **WHEN** a fenced line does not appear in the ledger
- **THEN** the draft is rejected naming the line
- **AND** the retry is attempted within the existing bound

#### Scenario: A URL that does not answer

- **WHEN** a ledgered URL fails the server's fetch
- **THEN** its entry is dropped before n8n reads the ledger
- **AND** a fence quoting that line is rejected

### Requirement: The review gate judges fidelity against the ledger

The review gate SHALL be handed the ledger and SHALL check that the draft's commands, versions and
manifest fields are the ones it names, rather than recalling the source material.

#### Scenario: A command the ledger does not carry

- **WHEN** the draft fences a flag or a version that no ledger entry names
- **THEN** the gate rejects the draft and names it

### Requirement: Outbound access is limited to declared source hosts

The article session SHALL fetch only from the hosts declared for it, and the limit SHALL be enforced
below the instruction — a proxy the container's tools go through — so a host off the list is refused
whether the server, a tool or the agent asked for it.

#### Scenario: A host outside the list

- **WHEN** a fetch names a host the deployment does not declare
- **THEN** the request is refused through the proxy and the refusal is logged with the host
- **AND** no bytes from that host reach the session

### Requirement: A quoted manifest is validated before it is fenced

A fenced YAML block SHALL be rendered or dry-run before it is written, and its ledger entry SHALL
record whether that validation ran and whether it failed. A block whose validation failed MUST NOT
appear in the article.

#### Scenario: A manifest that does not parse

- **WHEN** a quoted manifest fails the session's offline validation
- **THEN** the ledger records the failure
- **AND** the draft is rejected naming the block and the failure
