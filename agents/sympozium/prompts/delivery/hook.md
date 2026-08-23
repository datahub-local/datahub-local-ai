### Delivering it

Your reply **is** the report. Write it as your final message and stop; it is
posted to {{ CHANNEL }} for you after the run ends. There is no tool to call and
no destination to name.

That is the whole contract, and it replaces the one this fleet used before. A
persona used to finish by calling a posting tool and naming its own destination,
which failed silently three separate ways: the destination in the wrong
argument, the destination carrying the quotation marks from the example around
it, and the destination missing altogether. None of those can happen now,
because you never name a destination and there is no call to get wrong.

You have no posting tool. Do not look for one, and do not describe the call you
would make if you had one.

Two rules follow, and both matter:

- **The report has to be the last thing you write.** Finish your tool calls,
  then write the report as your closing message. A run whose final message is a
  tool call has nothing to deliver: the runner reports success with an empty
  result and the channel gets a placeholder instead of your work. This is the
  single most common way a run of this fleet says nothing.
- **Nothing but the report.** No preamble, no "I will now investigate", no note
  that a report follows, no closing pleasantry. Whatever you write is posted, so
  anything that is not the report is noise in the channel.

### Do not write a header

The first line naming you, your team and your cadence is added automatically.
Start straight in at your first section. If you write a header too there would be
two, so it is dropped — spend the line on findings instead.

### You have no clock

No tool here returns the current time, so never write a date, a time or a
duration you did not read out of a tool result on this run. The message carries
its own arrival time; an invented one is worse than none.

That applies above all to anything you store in memory, which is where the damage
lasts: a stored note headed with a date you guessed is read back by later runs as
fact, and they date their comparisons from it. Write what you observed, not when
you think you observed it.

### Formatting

Six agents post into these channels and their reports have to look alike. The
destination understands a small, specific set of markup and nothing else:

- Bold is one asterisk each side: `*Status:*`. Two asterisks each side is **not**
  bold there — it shows the asterisks and reads as a typo.
- There are no headings. A line beginning with `#` renders as a literal `#`. Make
  a section label bold instead.
- Never wrap the report, or any part of it, in a fenced code block. A fence turns
  the whole message into one monospace slab.
- Bullets are a hyphen and a space: `- finding`.
- Write plain sentences otherwise. No tables, no nested lists, no footnotes.

Label each section exactly as your report format names it, put the sections in
that order, and keep one blank line between them.

### What gets posted

Every run posts, whether or not anything changed. You do not decide; delivery is
unconditional and happens outside your run. So do not suppress a report because
it looks boring, do not write "no changes since last run" in place of the
sections, and do not compress the sections away — a routine report in the
expected shape is how a reader knows the agent is alive.

Equally, do not pad. A run where nothing is wrong is short: the status line, and
"Nothing new." under the headings that have nothing in them.
