# content-backlog Specification

## Purpose
TBD - created by archiving change add-article-audience-and-improvement-pass. Update Purpose after archive.

## Requirements

### Requirement: An imported row names its audience

An imported row SHALL carry the article lane's audience level — one of `NONE`, `LOW`, `MEDIUM`
or `ADVANCED` — taking the configured default when the board issue says nothing about it,
because a board issue is a title and a body and nothing else. The intake SHALL NOT judge or
infer the level: no model is consulted, and the row's level is the configured default until a
person changes it on the sheet. A person SHALL be able to change the level on the row after
import and before the lane picks it up.

The default SHALL be one of the levels the article lane accepts, and the level ids SHALL agree
between the intake's configured default, the article lane's validation and the lane's committed
audience definitions, so one value changes all three or none.

#### Scenario: An imported row carries the audience default

- **WHEN** a labelled issue is appended as an article row
- **THEN** the row carries the configured audience level
- **AND** no model was consulted to choose it

#### Scenario: The default is a level the lane accepts

- **WHEN** a row is imported with the default audience level
- **THEN** that level is one the article lane's definitions describe
- **AND** the lane does not refuse the row for its audience

#### Scenario: A person sets the level before the lane picks it up

- **WHEN** the audience cell of an imported row is edited on the sheet
- **THEN** the lane drafts for the edited level
- **AND** the intake does not overwrite it on a later run, whatever the issue's status

### Requirement: A labelled board issue enters the article queue exactly once

The board — the open issues labelled `post` in the configured repository — SHALL be read
and each issue that the article queue does not already carry SHALL be appended as one
`article_queue` row. The row SHALL carry the issue's own title as its topic, its body as
its description and its URL as its link, its status SHALL be queued, and it SHALL carry a
stable identifier of the issue so a later run recognises it. An issue the queue already
carries, matched by that identifier or by its link, MUST NOT be appended again. The read
SHALL be read-only: no issue SHALL be labelled, commented on, closed or otherwise written
to. A pull request returned by the issue read MUST NOT be imported.

#### Scenario: A new issue is imported

- **WHEN** an open issue labelled `post` is not in the article queue
- **THEN** one queued article_queue row is appended carrying its title, body and URL
- **AND** its identifier derives from the issue number

#### Scenario: An already-imported issue is skipped

- **WHEN** an issue's identifier or link is already present in the article queue whatever
  its status
- **THEN** no row is appended for it

#### Scenario: The board is not written to

- **WHEN** the board is read
- **THEN** no issue is labelled, commented on, or closed

#### Scenario: A pull request is not an article idea

- **WHEN** the issue read returns a pull request
- **THEN** it is not imported

### Requirement: An imported row carries everything the article lane needs

An imported row SHALL carry the fields the article lane reads — a topic or description, an
entry identifier, a category from the blog's own taxonomy, the requested asset types, a
word budget and a priority — and each SHALL take the configured default when the board
issue says nothing about it, because a board issue is a title and a body and nothing else.

#### Scenario: An issue with an empty body still imports

- **WHEN** a labelled issue carries no body
- **THEN** its row still carries its topic, link and identifier
- **AND** its remaining fields are the configured defaults

#### Scenario: The default category is one the lane accepts

- **WHEN** a row is imported with the default category
- **THEN** that category is one the article lane's taxonomy defines

### Requirement: A row still in play past the ceiling leaves the queue

A row that is still in play — queued, in progress, or awaiting approval — and whose last
update is older than the configured number of days SHALL be cancelled, in both the post
queue and the article queue. The age SHALL be measured from the row's own last update and
MUST NOT be measured from the source's date or the row's creation. A terminal row SHALL
NOT be cancelled, so re-running over a queue that has already been swept changes nothing.
An article row's cancellation SHALL set both its status and the article-lane field that
stops a claimed row being resumed.

#### Scenario: A queued row past the ceiling is cancelled

- **WHEN** a queued row's last update is older than the ceiling
- **THEN** its status becomes the queue's cancelled value
- **AND** no other field of the row is invented

#### Scenario: A stuck in-progress or unanswered approval is cancelled

- **WHEN** an in-progress or awaiting-approval row's last update is older than the ceiling
- **THEN** it is cancelled
- **AND** for an article row the field the article lane reads to resume a claim is cleared

#### Scenario: A live row is never cancelled

- **WHEN** a row's last update is within the ceiling, whatever its status
- **THEN** it is not cancelled

#### Scenario: Terminal rows are not revised

- **WHEN** a published, expired, errored or already-cancelled row is older than the ceiling
- **THEN** it is not written

### Requirement: The ceiling is one value, and one pass owns a row

Both queues SHALL use a single configured ceiling value, and the age-based retirement
SHALL be the only pass that writes a row past that ceiling, so the queue's per-hook expiry
and caps MUST NOT also select it. The ceiling SHALL be cancellable independently of the
per-hook expiry, which continues to govern which publishable rows are retained.

#### Scenario: One value for both queues

- **WHEN** the ceiling is changed
- **THEN** both queues use the new value without a second edit

#### Scenario: No row is written twice in one run

- **WHEN** a row is past the ceiling and would also be past its per-hook expiry
- **THEN** only the ceiling pass selects it
- **AND** the earlier expiry pass leaves it alone

### Requirement: A quiet board is still a run

The read of the board and of the queue SHALL both tolerate an empty result, so a run over
an empty board or an empty queue still performs the ceiling pass and still reports. A
failure of the intake SHALL reach a human through the workflow's error path.

#### Scenario: Nothing new on the board

- **WHEN** the board has no issue the queue does not already carry
- **THEN** no row is appended
- **AND** the ceiling still runs and the run still reports

#### Scenario: The queue is empty

- **WHEN** the queue has no rows
- **THEN** the ceiling pass is still reached
- **AND** the run does not stop at the empty read

#### Scenario: The intake fails

- **WHEN** the board read or the append fails
- **THEN** the failure is reported through the workflow's error path
