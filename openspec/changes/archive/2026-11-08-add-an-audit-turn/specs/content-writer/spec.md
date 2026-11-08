# Spec Delta

## ADDED Requirements

### Requirement: The draft is audited by a turn that can read the artifacts

Before a draft reaches a human, the adapter SHALL offer an `audit` task that runs in the draft's
session and working directory with tools enabled. It SHALL read the article, the derived ledger
and the session transcript, SHALL be able to fetch a page when neither settles a claim, and SHALL
answer the publish verdict together with a findings list. The findings SHALL reach the writer as
feedback on the next attempt. It SHALL NOT write the article, and it SHALL NOT report the counts
code already decides: budget, asset markers, fence-versus-ledger, heading numbering or the source
line.

#### Scenario: A claim no page carries

- **WHEN** the draft names a schedule, field or version that appears in no scraped page
- **THEN** the audit reports it as a finding naming the section
- **AND** the explanation the retry carries includes that finding

#### Scenario: A requested section that never landed

- **WHEN** the entry's feedback asks for a section the draft does not carry
- **THEN** the audit reports the missing section as the finding that blocks the draft

#### Scenario: The audit disagrees with the code gate

- **WHEN** the audit passes a draft the parser rejects
- **THEN** the parser's problem still rejects it, because the count is code's

### Requirement: The drafting turn can test its own fences before answering

The image SHALL carry a command that applies the server's own derivation to the article and the
session transcript, and the drafting prompt SHALL require it before the turn answers. A block it
reports as missing SHALL be quoted or turned into prose in that same turn.

#### Scenario: A fence no page carries

- **WHEN** the turn runs the command and a fenced block is on no scraped page
- **THEN** it prints a `MISSING:` line for that block
- **AND** the turn fixes it before answering, instead of losing the round
