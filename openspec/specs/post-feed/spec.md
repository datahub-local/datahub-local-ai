# post-feed Specification

## Purpose
The post feed's definition and selection: target topics, the company, reference-person and community source kinds, the cadence window each kind is admitted by, the stated company-vs-person balance and which part of it is enforced, and the per-source report that names the stage that stopped a source from reaching the queue.

## Requirements

### Requirement: The post feed has a written definition

The post feed SHALL be defined in the repository documentation as the `content_queue` post lane,
naming its target topics, its source kinds and the company-vs-person balance it is expected to
reach. A source SHALL be exactly one kind: a **company** (a subscribed Miniflux feed that is not a
reference person), a **reference person** (a feed named in the curator config), or **community**
(the Hacker News front page). Hacker News MUST NOT count as either a company or a person in the
balance.

#### Scenario: A newly subscribed feed

- **WHEN** a Miniflux feed is subscribed and is not listed as a reference person
- **THEN** it is classified as a company
- **AND** it keeps the company cadence window

#### Scenario: The balance is read

- **WHEN** a reader wants the feed's expected mix
- **THEN** the documented definition states the person share of the pool and of the backlog, and
  which of the two is enforced

### Requirement: Cadence is a window per source kind

The curator SHALL apply a company window and a wider person window, configured independently. The
intake query SHALL cover the wider window, and an entry SHALL be admitted only when it is inside the
window of its own kind, so a company entry outside the company window MUST NOT become a candidate
because the query was widened for people. Recency SHALL remain part of the pre-rank, so a person
post admitted by the wider window is ranked as the older post it is.

#### Scenario: A person entry older than the company window

- **WHEN** a reference person's entry is older than the company window and inside the person window
- **THEN** it is a candidate

#### Scenario: A company entry older than the company window

- **WHEN** a company's entry is older than the company window and inside the wider intake query
- **THEN** it is dropped before ranking
- **AND** the drop is counted against that feed as outside its window

#### Scenario: A slow writer's post is not called fresh

- **WHEN** a person post inside the wider window reaches the pre-rank
- **THEN** its age reduces its recency score
- **AND** its published date is carried to the queue unchanged

### Requirement: The company-vs-person balance is stated and observable

The config SHALL state a minimum person share of the pool and a minimum person share of the backlog.
The pool floor SHALL be reserved before category quotas are allocated, so a reference person is not
crowded out by companies that publish more often. The backlog target SHALL be reported and warned
against, and MUST NOT admit a row the judge rejected. Each run's report SHALL show, per category,
how many admitted candidates came from a company, a person or the community source.

#### Scenario: Companies rank higher than a person

- **WHEN** enough company candidates outrank a person candidate to fill the pool
- **THEN** the person pool floor still reserves the configured share for reference people
- **AND** the shortfall is reported when the pool cannot be filled

#### Scenario: The admitted mix falls short

- **WHEN** the admitted or backlog person share is under the configured target
- **THEN** the digest warns with both shares
- **AND** no rejected row is admitted to close the gap

#### Scenario: The mix is read per category

- **WHEN** a run admits candidates
- **THEN** the digest shows admitted people, companies and community rows per category

### Requirement: A per-source record is carried through every stage

The curator SHALL carry one per-feed record through fetch, filter, pool, judge and admission, and
each stage SHALL add its own counters to that record. A reference person the instance does not
subscribe SHALL have a record whose reason is `not subscribed`. A subscribed feed with nothing
inside its window SHALL have the reason `no items in window`.

#### Scenario: A reference person is missing from the instance

- **WHEN** the live feed list does not carry a reference person's feed
- **THEN** that person's record says `not subscribed`

#### Scenario: A feed is subscribed but quiet

- **WHEN** a subscribed feed produced entries but none inside its window
- **THEN** that feed's record says `no items in window`

### Requirement: The digest names why a reference person is absent

The digest SHALL list every reference person with no admitted row and the stage that stopped it, and
SHALL summarise the companies with no admitted row without letting that summary bury the person
list.

#### Scenario: A person reaches the pool and is cut later

- **WHEN** a reference person's candidate is in the pool but no row of theirs is admitted
- **THEN** the digest names the stage that stopped it after the pool
- **AND** the stage is one of the judge cut, judge blocked, judge unpostable or no backlog room
