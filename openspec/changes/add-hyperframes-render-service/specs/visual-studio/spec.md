# Spec Delta

## MODIFIED Requirements

### Requirement: Animation is rendered from a browser timeline

For an animated type rendered **in the workflow** the system SHALL render the markup in a browser, capture a deterministic sequence of frames at points on the animation timeline, and assemble the frames into one animated image. The number of frames, the frame rate and the duration SHALL be determined by the type and the content spec, not by wall-clock timing. In-workflow output SHALL be assembled in the format the type declares: a type declaring `webp` SHALL be assembled as an animated WebP, with animated GIF as the fallback when the WebP encoder is unavailable or fails, and a type declaring `gif` SHALL be assembled as an animated GIF directly, with animated WebP as the fallback when the GIF encoder is unavailable or fails. A **video type** is instead rendered by the visual render service (see the video requirement); the workflow MUST NOT encode video itself.

#### Scenario: Animated image produced
- **WHEN** an in-workflow animated type is produced
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

## ADDED Requirements

### Requirement: A video type is rendered by the render service

The registry SHALL be able to declare a video type, and when it is requested the workflow SHALL obtain the asset by posting the content spec to the visual render service and returning the resulting MP4, without building markup or capturing frames itself. The requested video type SHALL be reported unavailable if the service is not configured, and a service failure SHALL affect only that asset.

#### Scenario: Video produced by the service
- **WHEN** a video type is requested and the service is reachable
- **THEN** the asset is the MP4 the service returned
- **AND** the workflow performed no frame capture of its own

#### Scenario: Service failure is isolated
- **WHEN** the render service fails or is unreachable
- **THEN** the video asset carries the error
- **AND** every other requested asset is still produced

### Requirement: The studio sends only typed specs to the render service

The workflow MUST send the render service a content spec only; it MUST NOT forward raw markup or any model-authored string as executable content. The spec is validated before it is sent.

#### Scenario: Only a spec crosses the boundary
- **WHEN** the workflow calls the render service
- **THEN** the request body is a validated content spec and nothing executable

### Requirement: Diagram shape is declared in the spec

The content spec SHALL support a bounded vocabulary of diagram layouts — at minimum `stats` (a labelled figure list), `flow` (connected nodes in a sequence), `timeline` (ordered points along an axis), `comparison` (two opposed sides) and `bars` (values as proportional bars). An absent `layout` SHALL render as the default stats layout; a layout outside the vocabulary MUST fail loudly naming it.

#### Scenario: Layout drives the structure
- **WHEN** a spec declares a supported layout
- **THEN** the rendered asset uses that layout's structure rather than the default list

#### Scenario: Unknown layout
- **WHEN** a spec declares a layout not in the vocabulary
- **THEN** the run fails naming the unknown layout
- **AND** no asset is produced for it

### Requirement: Iconography and theme are bounded and validated

The spec SHALL support per-item icons drawn from a bounded, offline registry and a bounded theme (an accent, an optional second accent and an optional background). Every colour MUST be a valid hex value or the run fails loudly. An item naming an icon absent from the registry SHALL render without an icon rather than fail the run.

#### Scenario: Referenced icon is rendered
- **WHEN** a spec item names an icon in the registry
- **THEN** that glyph appears in the rendered asset
- **AND** no network is used to obtain it

#### Scenario: Unknown icon degrades
- **WHEN** a spec item names an icon not in the registry
- **THEN** the item renders without an icon
- **AND** the asset is still produced

#### Scenario: Invalid colour fails
- **WHEN** a spec supplies a colour that is not a valid hex value
- **THEN** the run fails naming the offending token

### Requirement: Structural motion is layout-driven and deterministic

The rendered asset SHALL support structural animations — connectors drawn, an arrow travelled from one node to the next, and an icon rotated — selected by the layout and the referenced icon, not authored by the model. Frame count, frame rate and duration SHALL derive from the type and the spec, never from wall-clock recording.

#### Scenario: A flow draws its connectors
- **WHEN** a `flow` asset is produced
- **THEN** its connectors animate as drawn and its nodes appear in reading order

#### Scenario: A spinning icon rotates
- **WHEN** an item references an icon declared as spinning
- **THEN** the glyph rotates over the asset's declared duration
