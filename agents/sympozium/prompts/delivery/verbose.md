### Posting it

Post the finished report with `send_channel_message`. Pass each value exactly as
written below, with nothing added around it — no quotation marks, no backticks,
no padding spaces:

    channel   slack
    chatId    {{ CHANNEL }}
    text      the report, exactly as written above - every section, in order,
             and under each finding the query you ran or the tool output the
             finding rests on, so a reader can check it without reopening the
             run

`channel` is the *transport* — one of whatsapp, telegram, discord, slack. It is
never a `#name`. The destination is `chatId`, and nothing else in the call
carries it.

Getting that one argument wrong is silent, and there are two ways to do it.
Omit `chatId` and the tool still answers `Message sent`, but it targets "owner
(self)": on a run you started yourself the report lands in the app's own direct
message, and on a scheduled run there is no owner at all, so Slack rejects it as
`channel_not_found` in a sidecar log nobody reads. Carry the punctuation that
surrounds the value in this file into the value itself and you get the same
rejection for the same reason — a channel by that name does not exist. Both look
exactly like a quiet, healthy run from the outside. Between them they are the
bug that kept every scheduled report from arriving.

If the tool returns an error, say so at the end of the report instead of
dropping it silently.
