# Spec Delta

## ADDED Requirements

### Requirement: An article that teaches a tool shows a block the reader can run

A draft whose shape teaches a tool SHALL carry at least one fenced block quoted from a page the run
fetched and ledgered. The block SHALL be verbatim: a name it needs is introduced in the prose above
it, because the ledger matches the block's words against the page and an edited block loses its
entry. A block that cannot run as written — elided lines, a missing import, an undefined name — is
a fragment and SHALL be written whole or left out.

The drafting prompt SHALL also ask for the failure the reader will meet, quoted from a fetched page
with its cause and fix, and for the version the article was checked against, as the source spells
it, in the section that first depends on one.

#### Scenario: A draft with no block where the shape teaches a tool

- **WHEN** the draft walks the reader through commands and fences nothing
- **THEN** the drafting prompt's block rule is the rule that was broken
- **AND** the retry carries the requirement

#### Scenario: A block is a fragment

- **WHEN** a fenced block carries an undefined name or an elided line
- **THEN** it is written whole with the name introduced in the prose above it, or it is cut

#### Scenario: No page states a version

- **WHEN** no fetched page carries a version string
- **THEN** the draft says nothing about versions

### Requirement: The title, a figure and a recommendation are held to a rule

The title SHALL name the subject and the specific thing the article settles, in at most twelve
words, and SHALL NOT be "A Guide to X" or a colon followed by a slogan. A number SHALL state what
was measured, on what, and where the figure comes from; a rounded figure used to sound large and a
range extrapolated from one data point SHALL NOT be written. When the body recommends a tool or an
approach it SHALL name where that choice is wrong and what to use instead. The close SHALL name the
page with the URL the run fetched, or the command to run now, and "see the documentation" SHALL NOT
serve as one.

#### Scenario: A title that fits another project

- **WHEN** the draft's title could headline an article about a different project
- **THEN** the review rejects the draft naming the title
- **AND** the improvement rewrites the title to the subject and its outcome

#### Scenario: A recommendation with no boundary

- **WHEN** the body recommends a tool and never says when not to use it
- **THEN** the review rejects the draft naming the recommendation
- **AND** the finding asks for the one line on the wrong choice

#### Scenario: A close that points nowhere

- **WHEN** the close says to read the documentation without naming the page
- **THEN** the review rejects the draft naming the close

### Requirement: A retry's lookups answer the feedback, not the old brief

A drafting retry SHALL fetch at most four pages, and only to answer a claim the reviewer feedback
names that the pages already held do not. A lookup the run has already answered SHALL NOT be
repeated.

#### Scenario: Feedback names a claim the run cannot source

- **WHEN** the feedback asks for a command the run never fetched
- **THEN** the retry fetches the page that carries it, within two lookups
- **AND** the block it writes is ledgered against that page

#### Scenario: Feedback asks for a restructure

- **WHEN** the feedback is about the article's shape and not about a fact
- **THEN** the retry fetches nothing

### Requirement: The ledger is re-read through the one path that leaves the pod

The session server SHALL verify a ledger through the Firecrawl MCP server when its endpoint is
configured, by calling `firecrawl_scrape` for each cited URL and matching the block on the scraped
markdown. It SHALL apply the source-host policy to the citation before any read, so the reader
widens the pod's reach and not what may be cited. With no endpoint configured it SHALL fall back to
the direct fetch and SHALL log at boot which path it uses.

#### Scenario: A pod with no internet egress

- **WHEN** the deployment carries only the MCP servers in the pod's egress policy
- **THEN** a ledgered URL is verified through the Firecrawl server, not a direct fetch
- **AND** a block the scraped page carries keeps its entry

#### Scenario: A scrape answers an error

- **WHEN** the Firecrawl call fails or answers unusable text
- **THEN** the entry is dropped with the failure named in the reason
- **AND** the drafting gate rejects the fence whose entry was dropped

#### Scenario: A citation off the declared hosts

- **WHEN** the ledger cites a host the request did not declare
- **THEN** the entry is dropped without a scrape being attempted
