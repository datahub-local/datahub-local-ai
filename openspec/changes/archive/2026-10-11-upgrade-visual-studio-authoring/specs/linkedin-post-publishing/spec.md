# Spec Delta

## ADDED Requirements

### Requirement: A video asset is published as a video post

When the media attached to a post is a video, the system SHALL publish it as a video
post, and when the media is an image or an animated image it SHALL publish it as an
image post. A single decision point SHALL choose the path from the asset's own media
type rather than from the requested type name. The node path handles images and
animated images; a video SHALL be uploaded through the LinkedIn API directly, because
the installed LinkedIn node supports only image and article posts. There SHALL be no
path that publishes by guessing the media type. The video upload path is
**[UNVERIFIED]** against LinkedIn — it is recorded as designed and has not been
exercised by a live public publish.

#### Scenario: A video asset publishes as video
- **WHEN** the approved asset's content type is `video/mp4`
- **THEN** the post is published with a video
- **AND** the asset is uploaded through the LinkedIn API video path

#### Scenario: An image asset still publishes as image
- **WHEN** the approved asset's content type is `image/gif` or `image/png`
- **THEN** the post is published with that image through the node
- **AND** the existing image path is unchanged

#### Scenario: The decision is the asset's media type
- **WHEN** the publish path is chosen
- **THEN** it is chosen from the asset's content type
- **AND** not from the requested type name

#### Scenario: The reviewer sees the video before approval
- **WHEN** a video asset is waiting for approval
- **THEN** it is uploaded for review before the approval decision
- **AND** the approval notice names the run and the media type
