Post the finished report to the Slack channel {{ CHANNEL }} with
`send_channel_message`. Send it exactly as written above — every section, in
order — and add, under each finding, the query you ran or the tool output the
finding rests on, so a reader can check it without reopening the run.

If the send fails, say so at the end of the report instead of dropping it
silently. A notification that failed and a run that found nothing look
identical from the outside.
