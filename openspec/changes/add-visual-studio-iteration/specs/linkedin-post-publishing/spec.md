# Spec Delta

## ADDED Requirements

### Requirement: A rejected animated asset continues its authoring session

The animated media branch SHALL request its asset under a session identifier derived
from the article it is publishing, so the first authoring and any later retry share
one session and a retry edits the composition the rejection named rather than
authoring a new one. The identifier SHALL NOT depend on the run that produced the
asset.

#### Scenario: A retry edits the rejected asset

- **WHEN** an animated asset is rejected and re-requested for the same article
- **THEN** the request carries the same session identifier as the first
- **AND** the composer continues from the composition it already produced

#### Scenario: The identifier does not depend on the run

- **WHEN** the animated asset is requested more than once for one article
- **THEN** the session identifier is the same each time
