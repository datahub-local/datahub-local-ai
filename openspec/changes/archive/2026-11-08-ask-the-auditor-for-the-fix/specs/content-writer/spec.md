# Spec Delta

## MODIFIED Requirements

### Requirement: The draft is audited by a turn that can read the artifacts

Before a draft reaches a human, the adapter SHALL offer an `audit` task that runs in the draft's
session and working directory with tools and the source proxy enabled. The adapter SHALL derive
the ledger before the audit and SHALL give it every fenced block no page carries together with the
URLs this session read. The audit SHALL answer the publish verdict and a findings list, and each
unquoted block SHALL become a finding naming its section and one fix: the page that carries the
block quoted verbatim, prose with no fence, or removal. A draft with any unquoted block SHALL NOT
carry a passing verdict, whatever the audit concluded. The findings SHALL reach the writer as
feedback on the next attempt. The audit SHALL NOT write the article, and SHALL NOT report the
counts code already decides: budget, asset markers, heading numbering or the source line.

#### Scenario: A block no page carries

- **WHEN** the draft fences a block that no page this session read contains
- **THEN** the audit's prompt carries that block and the pages read
- **AND** the finding names the page to quote, or says to write it as prose or cut it
- **AND** the verdict is false even when the audit answered true

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

#### Scenario: The audit's evidence is reachable

- **WHEN** the audit is told to search the session transcript or fetch a page
- **THEN** the transcript path is set in its environment and the proxy admits the declared hosts

## ADDED Requirements

### Requirement: The editing turn may fetch a page to quote it

The `improve` task SHALL run with tools and the same source allowlist as the draft, bounded to four
lookups, so a block a finding requires can be quoted byte for byte rather than invented or
dropped. It SHALL keep every fact from the draft, SHALL add a fenced block only as text a page it
fetched or a finding quotes verbatim, and SHALL run the self-check command before answering.

#### Scenario: A finding asks for a block

- **WHEN** a finding names a page whose block the draft must carry
- **THEN** the edit fetches that page and pastes its text byte for byte
- **AND** the self-check reports no missing block before it answers

#### Scenario: No page carries it

- **WHEN** neither the draft nor a page the run read carries the block a finding asks for
- **THEN** the edit writes the step in prose and adds no fence
