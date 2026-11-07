# Spec Delta

## ADDED Requirements

### Requirement: A session is bounded to one issue and its context stays small

A session SHALL carry one issue. The agent SHALL NOT run a second issue in it and
SHALL read an n8n workflow as `structure` or `filtered`, never `full`, and SHALL
NOT re-fetch one already in context. The adapter SHALL expose MCP tools through
Code Mode and SHALL summarize in the background as the default compaction
threshold approaches. The reviewer subagent SHALL return at most five findings,
one line each.

#### Scenario: A second issue arrives in a live session

- **WHEN** a prompt names an issue other than the session's issue
- **THEN** the agent reports the mismatch and does not start that work
- **AND** Hermes dispatches it in a new session

#### Scenario: The agent needs a workflow definition

- **WHEN** an n8n tool can answer the question
- **THEN** the request uses `structure` or `filtered`
- **AND** a workflow already in context is not fetched again

#### Scenario: The session reaches the compaction threshold

- **WHEN** the estimated context nears the default threshold
- **THEN** the summary is produced in the background
- **AND** the turn does not wait for it

#### Scenario: The reviewer reports

- **WHEN** the review subagent finishes
- **THEN** it returns at most five one-line findings and a verdict
