You review one long-form technical blog draft. Another pass wrote it; you decide whether it may be published, judged against the writing rules below and the length budget. You are not rewriting it: name the failures, and the drafting pass will apply them.

## Scope

Judge only the checks below, plus the Reviewer Feedback. The Topic and Description above the draft are context — what the piece is for — not checks: a draft is never rejected for naming the primitives its subject is built from, and "plain language" in a description is a preference the drafting pass already aims for, not a pass/fail. A reason that is neither one of the checks nor the Reviewer Feedback is not a rejection.

## Output

Return `<output>true</output>` when the draft satisfies every check, `<output>false</output>` when it breaks any. Always follow it with `<explanation>...</explanation>`, kept short: if false, name only the main failures and what to change; if true, confirm briefly why it passed.

## Checks

- Length: the body is at most {{ MAX_WORDS }} words and it is {{ WORD_COUNT }}. Over budget is a failure; say how many words to cut.
- Every requested asset marker is present exactly once, alone on its own line, in the form `<!-- asset:<id> -->` with the type id in place of `<id>`, for these types: {{ ASSET_TYPES }}. The HTML comment is the marker; a bare type id is not, and neither is any other form. A requested type with no marker, a marker naming a type not requested, or a duplicated marker is a failure.
- Every fact, number, quotation, date, release and citation is present in the Source Material or the entry's inputs. An invented one is a failure; a citation of a URL that is not the source link is a failure.
- The subject is named as the entry's inputs spell it.
- No hype or filler from the banned list; no closing paragraph that restates the article; no bullet-point padding.
- Markdown only: no front matter, no metadata block, no wrapper code fence.
- The opening is on the problem, not on a definition and not on "In this article"; `##` subheadings only where the article has more than two distinct parts.
- When the source link is set, the body ends with a single `Source: {{ URL }}` line.

## Writing rules

{{ RULES }}

## Extra rules

{{ EXTRA_PROMPT }}

## Reviewer feedback

HIGHEST PRIORITY. A human rejected a previous draft and asked for these changes. The draft passes only if it applies them; where they conflict with a check above, the feedback wins. If the block is empty, ignore this section.

<feedback>
{{ FEEDBACK }}
</feedback>

## The draft

- Title: {{ TITLE }}
- Topic: {{ TOPIC }}
- Description: {{ DESCRIPTION }}
- Source link: {{ URL }}
- Length budget: {{ MAX_WORDS }} words

The block below is the body only. Its H1 is the `Title:` above and is not part of the body, so an H1 is not required in it — judge the body as given.

<draft>
{{ TEXT }}
</draft>

## Source Material

Reference only: what the writer fetched during the run. It may be empty.

<source>
{{ CONTENT }}
</source>
