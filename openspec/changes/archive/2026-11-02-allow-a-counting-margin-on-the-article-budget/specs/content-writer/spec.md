# Spec Delta

## MODIFIED Requirements

### Requirement: Inputs are validated before drafting

The entry's length budget SHALL be enforced on the produced draft with a counting margin: a body of
at most ten percent over `MAX_WORDS` is the budget met, and a body past that limit MUST be retried
within the limit or fail loudly rather than silently overshoot. The limit SHALL be computed in the
same place the body is counted, and the review that decides acceptance SHALL be told the same limit
rather than the raw budget, so a reviewer cannot reject a draft the count accepts. The entry's
`CATEGORIES` SHALL be among the blog's existing categories or values the row explicitly declares; an
unknown category MUST be rejected before any commit.

#### Scenario: Draft inside the counting margin

- **WHEN** the produced draft is over `MAX_WORDS` but not over the ten percent limit
- **THEN** it is not rejected for length
- **AND** it is presented for review

#### Scenario: Draft over budget

- **WHEN** the produced draft is over the ten percent limit
- **THEN** the failure names the limit and the draft is retried
- **AND** nothing is presented for review with an out-of-budget draft

#### Scenario: Unknown category

- **WHEN** the draft names a category the blog does not define
- **THEN** the run records an error naming the category
- **AND** nothing is committed
