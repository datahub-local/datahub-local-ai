# Design

## Context

- `normalize_input` bounds a caller's `SCENES` to 1..12 and passes it on; a blank
  or non-positive value becomes `''`.
- `build_author_brief` turns it into one `sceneLine` string, used by all three
  authoring branches (the deck, the SVG and the rendered video). The line is the
  only place a caller's scene count reaches the composer.
- A duration extension already keys on the same count: a multi-scene clip is
  stretched so each scene gets the type's declared `secondsPerScene`.

## Goals / Non-Goals

**Goals:**

- A multi-scene clip opens on a title scene that names the subject.

**Non-Goals:**

- Changing the trigger contract, the type registry or the duration arithmetic.
- Guiding a blank scene count, when the count is the composer's own storyboard.

## Decisions

### D1. The title is an extra scene, not one of the declared count

A declared N yields N content scenes plus the title. *Alternatives considered:* make
the title the first of the N — rejected; the count names content items (a roundup's
count is the article's item count), so spending one on a title would drop an item.

### D2. The trigger is a declared count above one

Only `req.SCENES` drives it. When the count is blank the composer plans its own
scenes and this change adds no cue, because the brief cannot know how many scenes
that plan yields without pre-empting it. A count of one is a single item and needs
no introduction, so it is unchanged. *Alternatives considered:* guide any
multi-scene storyboard — rejected as scope; the caller's plan is the case with a
known answer.

### D3. One place, both node copies

The line is built once and shared by every branch, including the deck, whose title
scene reads as its title slide. The export carries the node twice, and the offline
test reads both copies — a fix applied to one is a live bug.

## Risks / Trade-offs

- **A shared `sceneLine` reaches the deck branch too.** → a deck's title scene is
  its title slide, and the paired video is authored from the same plan, so the two
  stay in step.
- **The count the composer renders may differ from the line.** → the line states
  the arithmetic explicitly (`scenes + 1`), so a wrong count is a prompt problem,
  not an ambiguity.

## Migration Plan

1. Edit `build_author_brief` in the export (both copies).
2. Run `test_visual_studio_graph.py` and `ruff check`.
3. Apply live with `scripts/apply_workflow_changes.py --require-edge`, then re-read
   and diff the export against live.

Rollback: revert the export edit and apply it back.

## Open Questions

- None.
