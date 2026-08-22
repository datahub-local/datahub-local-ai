Post the finished report to the Slack channel {{ CHANNEL }} with
`send_channel_message`, in short form: the status line and the findings only.

- Drop the recap sections — the ones that repeat what was already true on the
  last run.
- At most five bullets in total.
- No evidence lines, no query output, no reasoning.

Write the full report as normal in your run output; it is the *message* that is
short. If the send fails, say so at the end of the report instead of dropping
it silently.
