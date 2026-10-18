# Spec Delta

## ADDED Requirements

### Requirement: The requested asset set names each type once

The entry's requested asset set SHALL name each type exactly once, whatever the row's `ASSET_TYPES`
holds. A type listed twice SHALL NOT cause two studio calls, two asset rows, or two committed files
at one path, and every consumer of the set SHALL read the de-duplicated set rather than its own copy.

#### Scenario: A duplicated type is requested once

- **WHEN** the row's `ASSET_TYPES` names the same type twice
- **THEN** the requested set carries that type once
- **AND** the pending set, the publish gate and the commit path all see one entry for it

#### Scenario: A duplicated hero is one hero

- **WHEN** the row names the hero raster twice
- **THEN** the requested set carries the hero once
- **AND** the hero rule does not prepend a second one
