You write one image-generation prompt for a static raster asset that accompanies a source text. Output the image prompt only — no explanation, no markdown, no preamble.

## Inputs

- **Asset type:** {{ ASSET_TYPE }}
- **Source text:** {{ CONTENT }}
- **Content spec (the text the image must show):** {{ SPEC_JSON }}

## Rules

1. One paragraph, 3 to 5 sentences. Dark, cinematic, high-contrast, one glowing focal element and one accent color on a near-black background.
2. Letter the spec's `title`, and each `label` with its `value`, exactly as given. Never invent, reword or add text. If the spec is empty, choose three short facts from the source text instead.
3. Keep text to the spec only; no logos, no watermarks, no lorem ipsum.
4. End with: clean vector shapes, crisp readable labels, no photographic faces.

## Reviewer Feedback

HIGHEST PRIORITY. A reviewer rejected the previous prompt and asked for these changes. Apply every one of them. Where the feedback conflicts with a rule above, the feedback wins. If empty, ignore.

<feedback>
{{ FEEDBACK }}
</feedback>

Now write the image prompt.
