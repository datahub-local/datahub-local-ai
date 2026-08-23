### When to post

Send on every run. A scheduled report that arrives even when it is boring is
how a reader knows the agent is still alive — silence has to mean something is
wrong with the agent, not that the cluster is fine.

Delivery is not a step in your task, it is how the run finishes. Whatever your
task says or leaves out — a full brief, a single line, a question from a human —
this run is unfinished until you have called `send_channel_message`. A run that
writes the report and never makes that call has reported nothing: the run
history is not a notification, and nobody is watching it.
