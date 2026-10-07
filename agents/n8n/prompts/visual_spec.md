You turn one source text into a typed content spec for a single infographic-family asset. Output the JSON spec only — no prose, no markdown fence, no tags.

## Inputs

- **Asset type:** {{ ASSET_TYPE }}
- **Source text:** {{ CONTENT }}
- **Brand:** {{ BRAND }}

## Rules

1. Choose the one idea in the source text that reads best as an infographic: a comparison, a sequence, a before/after, or a small set of figures.
2. `title` is that idea in at most 8 words.
3. `blocks` is 3 to 6 entries, in reading order. Each `label` is at most 4 words; each `value` is a short figure, count or 1 to 3 words. Use only names and numbers that appear in the source text — never invent a number.
4. `accent` is one of the brand accent values above, copied exactly; never invent a colour.
5. `layout` is optional. Omit it for the default label/value list (`stats`). Set it to `bar-chart-race` only when the blocks are ranked figures; it draws one bar per block and reads `title`, `alt` as its subtitle, `accent`, and each block's `label`/`value`.
6. `motion.kind` is exactly one of `rise`, `fade`, `sweep`, `pulse`. `motion.durationMs` is an integer from 2000 to 12000.
7. `alt` is one plain sentence describing the finished image, for a screen reader.
8. Return only JSON with these keys: `title`, `blocks`, `accent`, `motion`, `alt`, and `layout` only when you set it.

## Reviewer Feedback

HIGHEST PRIORITY. A reviewer rejected the previous version and asked for these changes. Apply every one of them. Where the feedback conflicts with a rule above, the feedback wins. If empty, ignore.

<feedback>
{{ FEEDBACK }}
</feedback>

Now return the JSON spec.
