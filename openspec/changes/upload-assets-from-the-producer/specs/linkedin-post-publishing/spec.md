# Spec Delta

## ADDED Requirements

### Requirement: An approved asset is read from where the run stored it

The publish path SHALL read an approved asset's bytes from the object the run named, and
MUST NOT depend on the response carrying them. A still asset whose bytes are produced
inside n8n SHALL travel as binary and SHALL NOT travel as a data URL.

#### Scenario: An animated asset is fetched for publishing

- **WHEN** an approved animated asset is published
- **THEN** its bytes are fetched from object storage using the key the run returned
- **AND** no data URL is decoded anywhere in the path

#### Scenario: A still asset travels as binary

- **WHEN** the image creator returns an approved still asset
- **THEN** it carries the image as binary
- **AND** no data URL is built for it

#### Scenario: A missing object fails the publish

- **WHEN** the named object cannot be read
- **THEN** the publish fails with that reason
- **AND** it does not publish an empty or substituted media item
