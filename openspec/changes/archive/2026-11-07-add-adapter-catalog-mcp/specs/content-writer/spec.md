# Spec Delta

## MODIFIED Requirements

### Requirement: The writer researches within a bound and attributes what it read

The writer SHALL be able to search for the entry's subject and to read a page it found, within a bounded number of lookups per draft, and SHALL cite only pages it fetched during that run. A retrieved source SHALL be used only when it is about the entry's subject. When a search returns nothing usable or a source cannot be reached, drafting SHALL continue from the entry's inputs alone rather than from unread material. The drafting session SHALL reach the cluster's MCP catalog as well as the allowlisted HTTPS proxy: it MUST offer the catalog's GitHub read tools (`search_code`, `search_repositories`, `get_file_contents`, `list_branches`, `list_commits`, `list_tags`) and Firecrawl read tools (`firecrawl_search`, `firecrawl_scrape`, `firecrawl_map`) directly to the model, and MUST NOT expose any write tool on those servers. Every fenced block SHALL still name a URL the session server can refetch: a file read through the catalog is ledgered by its `https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>` address, and a documentation page by the page's own URL on a declared source host. A catalog search result is a pointer, not a source, and SHALL NOT be ledgered as one.

#### Scenario: A search finds a usable source

- **WHEN** the writer searches for the entry's subject and a result is about that subject
- **THEN** the writer reads the page before relying on it
- **AND** the draft cites it, and cites nothing it did not fetch

#### Scenario: Results are about a different subject

- **WHEN** every result shares the subject's name but is a different thing
- **THEN** the writer stops searching instead of hunting for a match
- **AND** the draft is written from the entry's inputs and cites no source

#### Scenario: A search source is unavailable

- **WHEN** one of the search sources cannot be reached in that run
- **THEN** the writer is told which source did not answer
- **AND** drafting continues from the sources that did
- **AND** when none answered, the draft is written from the entry's inputs alone

#### Scenario: A block was read through the catalog

- **WHEN** a fenced block came from `get_file_contents` or a Firecrawl read
- **THEN** its ledger URL answers the server's refetch
- **AND** a block whose ledger URL does not answer is dropped before n8n reads the ledger

#### Scenario: A write tool is named

- **WHEN** a drafting turn tries to reach a catalog write tool such as `create_or_update_file`
- **THEN** the tool is not declared to the model, because the server's exposure is `hidden` and only the read tools carry `direct` exposure

#### Scenario: The catalog does not answer

- **WHEN** a catalog server fails to connect
- **THEN** the turn continues through the allowlisted `curl` path
- **AND** the draft says in one sentence that the source could not be read when neither path answers
