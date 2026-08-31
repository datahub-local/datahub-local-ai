{{/*
  Small resolvers shared by ensembles.yaml and _delivery.tpl. Each takes one dict
  and returns a string, so callers read as one line.
*/}}

{{/*
  sympozium.cadence — a persona's schedule in words, for the report header.
  Read off the schedule rather than restated in a prompt, where it would drift
  from the cron the moment either changed.
  Args: schedule (the persona's schedule block, may be empty)
*/}}
{{- define "sympozium.cadence" -}}
{{- $s := .schedule | default dict -}}
{{- if $s.interval -}}
{{- printf "%s, every %s" $s.type $s.interval -}}
{{- else if $s.cron -}}
{{- printf "%s, cron %s UTC" $s.type $s.cron -}}
{{- else -}}
on demand
{{- end -}}
{{- end -}}

{{/*
  sympozium.deliveryKnob — one sympozium_delivery value for one persona, with the
  persona override winning over the ensemble default.
  Args: delivery, persona (name), knob, default
*/}}
{{- define "sympozium.deliveryKnob" -}}
{{- $pd := index (.delivery.personas | default dict) (.persona | toString) | default dict -}}
{{- index $pd .knob | default (index .delivery .knob) | default .default -}}
{{- end -}}

{{/*
  sympozium.deliveryMode — hook or reply.

  hook: a lifecycle.postRun container posts the run's own result straight to the
  Slack API. Nothing reaches the shared event bus, so the report arrives once.
  reply: the controller posts the run's own result back into the thread that
  asked, through the persona's channel sidecar.

  Neither posts by tool call: `send_channel_message` is off every allowlist, and
  the validator rejects it under both modes. It cost a duplicate copy of every
  report under the removed `tool` mode, and two lost answers under `reply`.

  hook is the default so a persona added later gets one-copy delivery without
  anyone remembering to ask. See ../README.md.
  Args: delivery, persona (name)
*/}}
{{- define "sympozium.deliveryMode" -}}
{{- include "sympozium.deliveryKnob" (dict "delivery" .delivery "persona" .persona "knob" "deliveryMode" "default" "hook") | lower -}}
{{- end -}}
