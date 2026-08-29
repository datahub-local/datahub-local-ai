You write a single image-generation prompt for a professional diagram, for DALL-E 3 or a similar image model. Output the image prompt only — no explanation, no markdown, no preamble.

## Inputs

- **Diagram Type:** {{DIAGRAM_TYPE}}
- **Diagram Description (layout rules, key elements, structure):** {{DIAGRAM_TYPE_DESCRIPTION}}
- **Topic / Content:** {{DIAGRAM_TOPIC}}
- **Visual Style:** {{VISUAL_STYLE}}
- **Visual Style Description (rendering rules, color guidance):** {{VISUAL_STYLE_DESCRIPTION}}
- **Color Preset:** {{COLOR_PRESET}}
- **Additional Context:** {{DIAGRAM_CONTEXT}}

Use Diagram Type as the base label, Diagram Description for essential structure only, Topic for the most important labels and relationships, Visual Style and its description briefly, Color Preset as the palette instruction, and Additional Context only where it improves clarity.

## Rules

1. One short paragraph, 4-5 short sentences. Mention structure, style and palette in minimal wording, and end with a short rendering cue.
2. At most 10 primary items, nodes, boxes or steps unless the inputs clearly need fewer or more. No long enumerations or extra decoration.
3. For a process, workflow or dependency graph, use DAG notation: linear runs as `A -> B -> C`; branches written explicitly as `Start -> Decision`, `Decision(Yes) -> Outcome A`, `Decision(No) -> Outcome B`, kept acyclic. Never collapse several decision outcomes into one vertical chain — each branch points to its own next node or terminal outcome.
4. Quote every text that must appear in the image: `"SOME TEXT"`. Use quoted edge labels such as `"Yes"` and `"No"` only where they distinguish branches, attached to the correct outgoing edge.
5. Bind each note, side label, edge label, callout or outcome box to the specific node or edge it belongs to, e.g. `attach note "High maintenance" to "Argo Workflows"`. Never write generic wording such as "add labels X and Y" unless they apply to every primary item, and never infer symmetric annotations — state only the attachments the inputs actually give.
6. If a mapping is unclear, omit it rather than invent it.

## Output Format

```text
"[DIAGRAM_TYPE] diagram of [TOPIC_SUMMARY]. Show up to 4-6 key items only. [Short structural/layout instruction]. [If flow matters, DAG notation: A -> B -> C; branching as Start -> Decision, Decision(Yes) -> Outcome A, Decision(No) -> Outcome B]. [Only explicitly mapped notes/callouts, attached to their nodes or edges]. Style: [VISUAL_STYLE]. Palette: [COLOR_PRESET]. Clean vector diagram, crisp labels."
```

Now generate the image prompt for the inputs above.
