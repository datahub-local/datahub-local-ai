#!/bin/sh
# Posts one agent run's report to Slack, once.
#
# Runs as a lifecycle.postRun container after the agent finishes. The report
# arrives in AGENT_RESULT; the destination and the header come from the env the
# chart sets. Nothing here touches Sympozium's event bus, which is the whole
# point: every channel sidecar delivers every instance's outbound message, so a
# report posted through the bus arrives once per bound persona. See
# ../MEMORY.md#every-report-arrived-five-times-and-only-one-agent-sent-it
#
#   AGENT_RESULT      the run's own final text (may be empty)
#   AGENT_LABEL       "<Agent> | <ensemble> | <cadence>", the header line
#   SLACK_CHANNEL     destination, e.g. #monitoring-ai-alerts
#   SLACK_BOT_TOKEN   from a Secret, by reference
set -eu

if [ -z "${AGENT_RESULT:-}" ]; then
  printf '%s' "Why do programmers prefer dark mode? Because light attracts bugs." > /tmp/raw
else
  printf '%s' "$AGENT_RESULT" > /tmp/raw
fi

# Slack speaks mrkdwn, not markdown, and a small model writes markdown. All
# three of these appeared in the first three real reports, so they are repaired
# here rather than only asked for in the prompt: a deterministic pass is what
# makes every message look the same.
#
#   fenced block   ->  dropped     (a fence renders the report as one grey slab)
#   **bold**       ->  *bold*      (two asterisks are not bold, they just show)
#   ## heading     ->  *heading*   (there are no headings; # renders literally)
#   * item         ->  - item      (one bullet character, consistently)
#   Label:         ->  *Label:*    (section labels bold, inline or on their own)
#
# Single quotes throughout: the fence pattern contains backticks, which inside
# double quotes would be command substitution.
sed -E '/^[[:space:]]*```[a-zA-Z0-9]*[[:space:]]*$/d' /tmp/raw > /tmp/nofence
sed -E \
  -e 's/\*\*([^*]+)\*\*/*\1*/g' \
  -e 's/^[[:space:]]*#{1,6}[[:space:]]*(.+)$/*\1*/' \
  -e 's/^[[:space:]]*[-*][[:space:]]+/- /' \
  -e 's/^([A-Z][A-Za-z ]{1,22}):[[:space:]]*$/*\1*/' \
  -e 's/^([A-Z][A-Za-z ]{1,22}):[[:space:]]+/*\1:* /' \
  /tmp/nofence > /tmp/norm

# The header is written here, not by the model: it is the one line that must
# always be right and every value is known exactly. Drop the model's own header
# if it wrote one anyway - matched on its two pipes - so there is never a pair.
sed -E '1{/^[[:space:]]*$/d}' /tmp/norm \
  | sed -E '1{/^\*?[^|]+\|[^|]+\|.*$/d}' \
  | sed -E '1{/^[[:space:]]*$/d}' > /tmp/body

{ printf '*%s*\n\n' "$AGENT_LABEL"; cat /tmp/body; } > /tmp/msg

# A delivery failure has to be loud: postRun failures are recorded as Conditions
# on the run, and that is the only place a dropped report leaves a trace.
OUT=$(curl -sS --max-time 30 -X POST https://slack.com/api/chat.postMessage \
        -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
        --data-urlencode "channel=$SLACK_CHANNEL" \
        --data-urlencode "mrkdwn=true" \
        --data-urlencode "text@/tmp/msg")
echo "slack response: $OUT"
echo "$OUT" | grep -q '"ok":true' || { echo "DELIVERY FAILED"; exit 1; }
echo "delivered ok"
