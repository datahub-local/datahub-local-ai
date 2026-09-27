You turn one source text into a typed content spec for a single infographic-family asset. Output the JSON spec only — no prose, no markdown fence, no tags.

## Inputs

- **Asset type:** {{ ASSET_TYPE }}
- **Source text:** {{ CONTENT }}

## Rules

1. Choose the one idea in the source text that reads best as an infographic: a comparison, a sequence, a before/after, or a small set of figures.
2. `title` is that idea in at most 8 words.
3. `blocks` is 3 to 6 entries, in reading order. Each `label` is at most 4 words; each `value` is a short figure, count or 1 to 3 words. Use only names and numbers that appear in the source text — never invent a number.
4. `accent` is one 6-digit hex color, dark-themed and readable on a near-black page, e.g. `#22d3ee`.
5. `motion.kind` is exactly one of `rise`, `fade`, `sweep`, `pulse`. `motion.durationMs` is an integer from 2000 to 4000.
6. `alt` is one plain sentence describing the finished image, for a screen reader.
7. Return only JSON with exactly these keys: `title`, `blocks`, `accent`, `motion`, `alt`.

## Reviewer Feedback

HIGHEST PRIORITY. A reviewer rejected the previous version and asked for these changes. Apply every one of them. Where the feedback conflicts with a rule above, the feedback wins. If empty, ignore.

<feedback>
{{ FEEDBACK }}
</feedback>

Now return the JSON spec.
