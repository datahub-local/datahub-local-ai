# Spec Delta

## ADDED Requirements

### Requirement: The drafting prompt belongs to the writer adapter

The article's drafting prompt, the shapes it may choose from and the audience levels SHALL live in
the writer adapter's image, and the caller SHALL send the entry's fields rather than prompt text. A
prompt edit SHALL take effect with the image, without a workflow change. The review and the
improvement pass SHALL read the same committed rules file the adapter renders, so no second copy
exists.

#### Scenario: The creator posts a turn

- **WHEN** `Article Creator` requests a draft
- **THEN** the body carries the entry's fields, the session id, the attempt and the source hosts
- **AND** it carries no prompt text

#### Scenario: A prompt file changes

- **WHEN** the adapter's prompt file changes and the image is rebuilt
- **THEN** the drafting prompt changes
- **AND** no n8n workflow changes with it

#### Scenario: The gate reads the writer's rules

- **WHEN** the reviewer's prompt is composed
- **THEN** `RULES` is the adapter's `article_writer_system.md`
- **AND** no second copy of those rules exists in `agents/n8n/prompts/`

#### Scenario: A missing entry field

- **WHEN** the brief omits a field the task template names
- **THEN** the field renders empty
- **AND** the turn still writes the article from the fields it was given
