# Spec Delta

## Purpose

Turns one source text into a self-contained, navigable HTML presentation authored for
that text, and renders the same plan to a video in the same authoring run. A deck is an
artifact a person opens and steps through; the paired video is the same plan for
anywhere a file is attached. Neither is templated: the deck is authored for the text.

## ADDED Requirements

### Requirement: A source text can be authored as a presentation

The system SHALL support producing a presentation by authoring a navigable HTML deck
for a source text, rather than selecting a template or a set of slides. The deck SHALL
be the artifact of record, and the plan (the arc, the per-slide content and the
transitions) SHALL be stated before it is authored and recorded with the run.

#### Scenario: A deck is authored, not templated
- **WHEN** a presentation is requested for a source text
- **THEN** a deck is authored for that text
- **AND** the workflow performed no markup generation of its own

#### Scenario: The plan is stated first
- **WHEN** a deck is authored
- **THEN** its arc and slides are stated before the deck is written
- **AND** the plan is recorded with the run

### Requirement: A deck is self-contained and opens offline

A deck SHALL be one self-contained file: no external stylesheet, script, font or
network request at open time. It SHALL be readable with the text's own structure
preserved — one idea per slide — and its navigation SHALL work without a server.

#### Scenario: One file
- **WHEN** a deck is produced
- **THEN** it is a single file
- **AND** it opens with no network available

#### Scenario: A remote reference
- **WHEN** an authored deck references a remote resource
- **THEN** the attempt is reported as a failure
- **AND** no deck is returned from it

### Requirement: A deck run also yields a video of the same plan

The same authoring run that produces a deck SHALL also render that plan to a video, so
the two artifacts agree and the caller pays one authoring turn. The video SHALL NOT be
authored separately from the deck.

#### Scenario: Both artifacts come from one run
- **WHEN** a deck is requested
- **THEN** the run returns the deck and a video of the same plan
- **AND** the two were authored in one turn

#### Scenario: The video carries the deck's content
- **WHEN** the paired video is reviewed against its deck
- **THEN** the slides and their order match
- **AND** the video is not a different treatment of the source text
