{{/*
  How a report reaches its channel: the prompt text that tells the model its part,
  and the postRun container that does the posting.

  Both halves are here because they are two ends of one contract — change what the
  hook does and the prompt has to say so. The prose the model reads is in
  prompts/delivery/hook.md; the posting itself in files/deliver-slack.py.
*/}}

{{/*
  sympozium.deliveryBlock — the text substituted into a persona's {{ DELIVERY }}.

  hook.md alone. The hook writes the header itself, so the persona is told not to,
  and hook.md carries the no-clock rule. reply-mode personas get no block at all;
  their prompt carries its own answering contract.
  Args: root
*/}}
{{- define "sympozium.deliveryBlock" -}}
{{- $hook := .root.Files.Get "prompts/delivery/hook.md" -}}
{{- if not $hook }}{{ fail "prompts/delivery/hook.md is missing or empty" }}{{ end -}}
{{- trimSuffix "\n" $hook -}}
{{- end -}}

{{/*
  sympozium.deliveryHook — the postRun container, as YAML for the caller to
  fromYaml. The script is a real file rather than an inline string so it can be
  read, linted and tested on its own; see files/deliver-slack.py.

  The token is referenced, never inlined, so no credential enters the chart.
  Egress reaches slack.com because this pod carries no sympozium.ai/role=agent
  label and so escapes sympozium-agent-deny-all.
  Args: root, channel, label
*/}}
{{- define "sympozium.deliveryHook" -}}
{{- $h := .root.Values.sympozium_delivery_hook | default dict -}}
{{- if not $h.secret }}{{ fail "deliveryMode is hook, but sympozium_delivery_hook.secret is unset, so the hook has no bot token" }}{{ end -}}
{{- $script := .root.Files.Get "files/deliver-slack.py" -}}
{{- if not $script }}{{ fail "files/deliver-slack.py is missing or empty (is it excluded by .helmignore?)" }}{{ end }}
name: deliver
image: {{ $h.image | default "python:3.13-alpine" | quote }}
command: ["python3", "-c"]
args:
  - |
{{ $script | indent 4 }}
env:
  - name: SLACK_CHANNEL
    value: {{ .channel | quote }}
  - name: AGENT_LABEL
    value: {{ .label | quote }}
  - name: SLACK_BOT_TOKEN
    valueFrom:
      secretKeyRef:
        name: {{ $h.secret | quote }}
        key: {{ $h.tokenKey | default "SLACK_BOT_TOKEN" | quote }}
{{- end -}}
