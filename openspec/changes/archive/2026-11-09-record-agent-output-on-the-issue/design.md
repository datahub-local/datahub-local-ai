# Design

## One comment per round, on the issue

The owner watches the issue. The reviewer watches the pull request. A fix round
already writes its detail in the review conversation and the second-model review,
so repeating that on the issue is noise. The issue comment carries the three facts
the owner acts on:

- the fix happened, one line per item;
- the gate still passes, with the command and its result;
- nothing else, no code, no diff.

## Who writes it

The agent, not Hermes. Hermes sees a session end and a pull request, but not which
findings were fixed or which gate was run. The agent has that context, and the
`taskboard` skill already owns every issue comment it writes. `review` points at
the same section so a second-model fix round is not a second shape.

## Not duplicating the announcement

The tick comments the full pull request URL when the pull request is new. After
that, the URL is already on the issue, and re-posting it on every return to review
turns the thread into a list of the same link. The tick's step 5 checks for the URL
and leaves the fix comment as the record.

## The marker

Every agent comment ends with `<!-- taskboard:agent -->`. It is what keeps the tick
from reading the comment as the owner's answer and re-forwarding it to the agent
that just wrote it.

## The answer that never left the session

The `question` tool returns its answer in-process when the owner picks an option in
the web UI. Hermes is not in that loop: it polls `get_session` on a ten-minute tick
and publishes `needs_input`, which the owner can beat by answering immediately. The
agent is the only process that sees both the question and the answer, so it writes
the decision on the issue. An answer that arrives as a prompt is different: it was
relayed from the issue or Slack, already on the record, and repeating it would be
noise.
