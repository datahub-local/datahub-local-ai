# Spec Delta

## ADDED Requirements

### Requirement: The writer chooses the visual form from the post it wrote

The post draft SHALL answer the visual form beside the hook, as `<form>ID</form>` after the
`</output>` block, from the vocabulary in `visual_forms.md`. The choice SHALL follow the post's
argument, not the article's topic. An id outside the offered list SHALL fail by name. The row's
pinned form SHALL win over the writer's choice; the hook's `visual` SHALL be the fallback when the
writer names none and the row is empty.

#### Scenario: A post whose argument is a sequence
- **WHEN** the post's spine is a sequence, a mechanism or a failure over time
- **THEN** the writer answers `story` and the media branch renders a story, not a static diagram

#### Scenario: The row pins the form
- **WHEN** `content_queue.VISUAL_FORM` carries a form
- **THEN** the pinned form is used and the writer's answer does not overwrite it

#### Scenario: The writer answers no form
- **WHEN** the answer carries no `<form>` tag and the row is empty
- **THEN** the hook's `visual` default is used, and the run does not fail

#### Scenario: The writer names an unknown form
- **WHEN** the answer names a form the brief's list does not carry
- **THEN** the turn fails by name rather than writing a blank or an invalid cell
