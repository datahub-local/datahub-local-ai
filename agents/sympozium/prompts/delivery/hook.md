### Delivering it

Your reply is the report. Write it as your final message and stop; it is posted
to {{ CHANNEL }} for you after the run ends. There is no tool to call and no
destination to name.

- The report must be your last message. A run ending on a tool call delivers
  nothing: the runner reports success with an empty result.
- Write nothing but the report. No preamble, no "I will now investigate", no
  closing pleasantry. Everything you write is posted.
- Do not write a header. The line naming you, your team and your cadence is
  added for you. Start at your first section.

### You have no clock

No tool here returns the current time. Never write a date, time or duration you
did not read from a tool result on this run, above all in anything you store in
memory: later runs read a guessed date back as fact.

### Shape

Line one is the outcome: `**Status:**` then one sentence saying what a person has
to act on this run, or that nothing needs action. Never a figure that appears
again below, and never a section that opens on its label alone.

Then your own format's sections, in its order, under its exact labels. The whole
report is at most 250 words. Your format may state a tighter cap; it never
raises this one.

A check that failed, or a figure no tool answered, is a **gap**, and gaps are not
part of the outcome. Write the outcome, end that line with `(*)`, and list every
gap once in one footnote block after your last section:

    **Status:** Prometheus is at 91% of its limit; cut retention or grow the PVC. (*)
    ...
    (*) `pg_get_top_queries` failed: `ERROR:` `pg_stat_statements` is not installed.

Keep the literal `ERROR:` in the footnote for a failed check; it is what carries
the red verdict. No gap: no `(*)` and no footnote.

- One fact, once. A section that would repeat what an earlier section said leaves
  it out, and says nothing about leaving it out.
- One condition on several machines is one bullet: the machines as a comma list,
  and the cause and the action once. Never one bullet per machine per check.
- Name the worst and count the rest — `worst prometheus 81.9% (+1.9pp), 30 others
  0.8-55.7%` — never a tool's whole column.
- A bullet is one line where it can be, never more than two. No paragraph over
  three lines.
- State the reading, not the reassurance. `0 evictions` is the reading; why that
  is fine is commentary.
- Name the source, never quote it: `facts_volume_fill`, not a pasted row.
- Over 250 words: cut healthy detail to one line first, then the smaller figures,
  then shorten machine lists. Never drop a finding, an action, the outcome line,
  or a gap you already marked `(*)`.

### Formatting

Write standard Markdown. It is converted for the channel after the run, so write
Markdown and nothing else; you do not need to know what the channel accepts.

- `**bold**` for emphasis, `##` for a section label, `- ` for a bullet.
- No HTML tags of any kind. No tables, no nested lists, no footnotes.
- Never retype a tool's table or a row of one. Write only the figures you make a
  claim about, next to the claim.
- Label each section exactly as your report format names it, keep that order,
  one blank line between sections.

### What gets posted

Every run posts, changed or not. Do not suppress a report, do not replace the
sections with "no changes since last run", and do not drop a section. Do not pad
either: a clean run is the status line and `Nothing new.` under empty headings.
