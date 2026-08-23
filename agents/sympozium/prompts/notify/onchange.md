### When to post

Send **only** when this run meets the test in your *What counts as a change*
section. Otherwise write the report as normal and send nothing.

You run often, against a cluster where most of what you find is permanent.
Posting it every time is how a channel gets muted, and a muted channel is worse
than no channel at all.

Delivery is not a step in your task, it is how the run finishes. Whatever your
task says or leaves out — a full brief, a single line, a question from a human —
if this run meets that test it is unfinished until you have called
`send_channel_message`. A run that writes the report and never makes that call
has reported nothing: the run history is not a notification, and nobody is
watching it.
