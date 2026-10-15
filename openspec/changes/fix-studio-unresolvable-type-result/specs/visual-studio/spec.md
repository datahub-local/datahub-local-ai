# Spec Delta

## REMOVED Requirements

### Requirement: A declared-but-unavailable type is reported

WHEN a requested type is declared but not producible in the current environment, the system SHALL report it as unavailable with a reason and MUST NOT fail the run or block the other assets.

#### Scenario: An agent type requested without a composer session
- **WHEN** an agent-authored type is requested and the composer session address is not configured
- **THEN** it is reported unavailable with a reason
- **AND** the requested image is still produced

## ADDED Requirements

### Requirement: A type the registry cannot resolve is reported

WHEN a requested type cannot be resolved — an id the registry does not declare, or one
declared but not producible in the current environment — the system SHALL answer with an
asset carrying that id and a reason, and MUST NOT fail the run or block any other
requested asset. The answer SHALL be an asset in the run's asset list: an empty result is
not a report, and a caller may not have to distinguish "nothing was produced" from "no
answer was given".

#### Scenario: An agent type requested without a composer session
- **WHEN** an agent-authored type is requested and the composer session address is not configured
- **THEN** it is reported unavailable with a reason
- **AND** the requested image is still produced

#### Scenario: The only requested type cannot be resolved
- **WHEN** a request asks for one type the registry cannot resolve and nothing else
- **THEN** the run answers with that type's asset, carrying a reason that names it
- **AND** the run status reports the failure
- **AND** the caller sees the reason rather than an empty result
