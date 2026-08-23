### Posting it

Post the finished report with `send_channel_message`, called with exactly these
arguments:

    channel: "slack"
    chatId:  "{{ CHANNEL }}"
    text:    the report, exactly as written above — every section, in order

`channel` is the *transport* — one of whatsapp, telegram, discord, slack. It is
never a `#name`. The destination is `chatId`, and nothing else in the call
carries it.

Getting that one argument wrong is silent. Omit `chatId` and the tool still
answers `Message sent`, but it targets "owner (self)": on a run you started
yourself the report lands in the app's own direct message, and on a scheduled
run there is no owner at all, so Slack rejects it as `channel_not_found` in a
sidecar log nobody reads. Both look exactly like a quiet, healthy run from the
outside. This is the bug that kept every scheduled report from arriving.

Send the report itself — not a summary of it, and not a note saying that a
report exists. If the tool returns an error, say so at the end of the report
instead of dropping it silently.
