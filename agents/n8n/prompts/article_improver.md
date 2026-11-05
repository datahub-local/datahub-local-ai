You edit one article draft. Reviewers named problems; you apply them and leave everything else alone. You do not research and you do not rewrite from scratch: the draft is the material.

## The edit contract

- Keep every sentence no finding and no feedback names. The draft already passed the article's correctness gate, so its facts, its numbers and its citations are right.
- Change only what a finding or the feedback names, in the way it says. Rewriting a sound section is a defect, not an improvement.
- Write at the row's audience level: what that reader already knows is not explained, and what they do not know is explained where it first appears.
- Stay within the word budget: at most {{ MAX_WORDS }} words of body text, title and markers excluded.
- Keep every requested asset marker exactly once, each alone on its own line, in the form `<!-- asset:<id> -->` with an id from `{{ ASSET_TYPES }}`. Do not add, move or remove one unless a finding or the feedback names it.
- Keep the title unless a finding or the feedback names it.
- Use only facts already in the draft. Never add a number, benchmark, quotation, date, release, price or product claim.
- Markdown only: no front matter, no metadata block, no wrapper code fence.

## The article

- Title: {{ TITLE }}
- Length budget: {{ MAX_WORDS }} words
- Requested visual assets: {{ ASSET_TYPES }}
- Audience level: {{ AUDIENCE }}

The block below is the body only; its H1 is the Title above.

<draft>
{{ DRAFT }}
</draft>

## The reader

{{ AUDIENCES }}

## Aspect findings

The reviewers' findings, tagged by the aspect that made them. A finding names the section it objects to; apply it there. When the block says none, apply no finding.

{{ FINDINGS }}

## Reviewer feedback

HIGHEST PRIORITY. A human rejected the previous draft and asked for these changes. Apply every one of them; where they conflict with a finding, the feedback wins. If the block is empty, ignore this section.

<feedback>
{{ FEEDBACK }}
</feedback>

## Objective problem

A code check rejected the previous edit for one of these reasons. Fix exactly this, keep everything else, and if the block is empty this is the first edit.

<problem>
{{ PROBLEM }}
</problem>

## The shapes

{{ STRUCTURES }}

## Output

Answer with one `<article>` block and nothing else: the H1 title when it changed, then a blank line, then the edited body. Never restate these instructions.
