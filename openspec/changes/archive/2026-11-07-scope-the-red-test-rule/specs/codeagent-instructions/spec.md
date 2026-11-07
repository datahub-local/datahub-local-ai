# Spec Delta

## MODIFIED Requirements

### Requirement: Tests cover behaviour, never configuration

A test SHALL assert what the code does, SHALL fail without the change, and SHALL NOT
assert a YAML value, a chart option, a prompt's wording or a file's presence. The
agent SHALL run the gate the repository's own `AGENTS.md` names, and SHALL NOT make
a gate pass by skipping a test, widening a lint rule or loosening an assertion. A test
that asserts configuration SHALL be deleted with the rule that forbade it; deleting a
test that covers behaviour to make a gate pass remains forbidden.

#### Scenario: A rule file changes

- **WHEN** the change is to instructions, documentation or configuration
- **THEN** no test asserts their wording
- **AND** the repository's render or build gate is the check

#### Scenario: A test is red

- **WHEN** the gate fails on a test that asserts what the code does
- **THEN** the agent fixes or reports it
- **AND** it does not skip, relax or delete that test

#### Scenario: A configuration test is red

- **WHEN** a test asserts a prompt, a dataset, a config value or a committed workflow export
- **THEN** it is deleted with the rule that forbade the test
- **AND** the behaviour it was standing in for is checked by the build or the live run
