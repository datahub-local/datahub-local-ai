# Spec Delta

## MODIFIED Requirements

### Requirement: Animation is rendered from a browser timeline

For an animated type the system SHALL render the markup in a browser, capture a deterministic sequence of frames at points on the animation timeline, and assemble the frames into one animated image. The number of frames, the frame rate and the duration SHALL be determined by the type and the content spec, not by wall-clock timing. The assembled format SHALL be the one the type declares: a type declaring `webp` SHALL be assembled as an animated WebP, with animated GIF as the fallback when the WebP encoder is unavailable or fails, and a type declaring `gif` SHALL be assembled as an animated GIF directly, with animated WebP as the fallback when the GIF encoder is unavailable or fails.

#### Scenario: Animated image produced
- **WHEN** an animated type is produced
- **THEN** the captured frames are assembled into a playable animated file
- **AND** its duration matches the value declared for the asset

#### Scenario: Declared format selects the encoder
- **WHEN** an animated type declares GIF as its format
- **THEN** its frames are assembled as an animated GIF
- **AND** no WebP file is used as that asset's output

#### Scenario: Frame capture fails
- **WHEN** the browser render or the frame capture fails
- **THEN** that asset carries the error
- **AND** every other asset of the request is unaffected
