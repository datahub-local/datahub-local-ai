# Spec Delta

## ADDED Requirements

### Requirement: An approved asset is read from where the run stored it

The publish path SHALL read an approved asset's bytes from the object the run named, and
MUST NOT depend on the response carrying them. It SHALL obtain a short-lived signed URL
from the service that holds the bucket credential, so the workflow needs no bucket
credential of its own.

#### Scenario: An animated asset is fetched for publishing

- **WHEN** an approved animated asset is published
- **THEN** a signed URL is obtained for the key the run returned
- **AND** the bytes are fetched from it as binary for the upload
- **AND** no data URL is decoded anywhere in the path

#### Scenario: The media type is the asset's own

- **WHEN** the publish path chooses between the video and image paths
- **THEN** it reads the media type the run recorded for the asset
- **AND** it does not read it from the node that downloaded the bytes, which carries no
  JSON of its own

#### Scenario: A missing object fails the publish

- **WHEN** the named object cannot be read
- **THEN** the publish fails with that reason
- **AND** it does not publish an empty or substituted media item
