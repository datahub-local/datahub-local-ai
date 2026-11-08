# Spec Delta

## ADDED Requirements

### Requirement: The source ledger is derived from the turn's transcript

The session server SHALL write `sources.json` itself, from the pages the turn actually scraped:
for every fenced block in the article it SHALL search the text the model received for that page
and SHALL record one entry naming the page when the block appears on it. A block that appears on
no scraped page SHALL get no entry, which the gate reports as unquoted. The model SHALL NOT be
asked to write the ledger, and no separate fetch SHALL be made to verify a page the pod already
brokered.

#### Scenario: A quoted block

- **WHEN** the article fences a block that appears in a page the turn scraped
- **THEN** the ledger carries one entry with that block and that page's URL
- **AND** the entry is written by the server, not returned by the model

#### Scenario: An invented block

- **WHEN** the article fences a heredoc the model assembled from several pages
- **THEN** no entry is written for it
- **AND** the gate rejects the draft naming the block as unquoted

#### Scenario: Text the model never received

- **WHEN** a block would match only the part of a page beyond the truncation the model saw
- **THEN** the block is not verified, because it was never read
