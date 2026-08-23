{{/*
  How a report reaches its channel: the prompt text that tells the model its part,
  and the postRun container that does the posting.

  Both halves are here because they are two ends of one contract — change what the
  hook does and the prompt has to say so. The prose the model reads lives in
  prompts/delivery/ and prompts/notify/; the posting itself in
  files/deliver-slack.sh. This file only assembles them.
*/}}

{{/*
  sympozium.deliveryBlock — the text substituted into a persona's {{ DELIVERY }}.

  hook mode is hook.md alone. It deliberately excludes header.md, because the hook
  writes the header itself and a persona told to write one too would produce a
  pair; hook.md therefore carries the no-clock rule that header.md holds for tool
  mode. Handing a small model both sets would hand it a contradiction: under a
  hook it has no posting tool and cannot suppress a run.

  tool mode is header + verbosity + notify, the original three-file block.
  Args: root, mode, verbosity, notify
*/}}
{{- define "sympozium.deliveryBlock" -}}
{{- $root := .root -}}
{{- if eq .mode "hook" -}}
{{- $hook := $root.Files.Get "prompts/delivery/hook.md" -}}
{{- if not $hook }}{{ fail "prompts/delivery/hook.md is missing or empty" }}{{ end -}}
{{- trimSuffix "\n" $hook -}}
{{- else -}}
{{- $header := $root.Files.Get "prompts/delivery/header.md" -}}
{{- if not $header }}{{ fail "prompts/delivery/header.md is missing or empty" }}{{ end -}}
{{- $verbosity := $root.Files.Get (printf "prompts/delivery/%s.md" .verbosity) -}}
{{- if not $verbosity }}{{ fail (printf "verbosity %q has no prompts/delivery/%s.md" .verbosity .verbosity) }}{{ end -}}
{{- $notify := $root.Files.Get (printf "prompts/notify/%s.md" .notify) -}}
{{- if not $notify }}{{ fail (printf "notify %q has no prompts/notify/%s.md" .notify .notify) }}{{ end -}}
{{- printf "%s\n\n%s\n\n%s" (trimSuffix "\n" $header) (trimSuffix "\n" $verbosity) (trimSuffix "\n" $notify) -}}
{{- end -}}
{{- end -}}

{{/*
  sympozium.deliveryHook — the postRun container, as YAML for the caller to
  fromYaml. The script is a real file rather than an inline string so it can be
  read, linted and tested on its own; see files/deliver-slack.sh.

  The token is referenced, never inlined, so no credential enters the chart.
  Egress reaches slack.com because this pod carries no sympozium.ai/role=agent
  label and so escapes sympozium-agent-deny-all.
  Args: root, channel, label
*/}}
{{- define "sympozium.deliveryHook" -}}
{{- $h := .root.Values.sympozium_delivery_hook | default dict -}}
{{- if not $h.secret }}{{ fail "deliveryMode is hook, but sympozium_delivery_hook.secret is unset, so the hook has no bot token" }}{{ end -}}
{{- $script := .root.Files.Get "files/deliver-slack.sh" -}}
{{- if not $script }}{{ fail "files/deliver-slack.sh is missing or empty (is it excluded by .helmignore?)" }}{{ end }}
name: deliver
image: {{ $h.image | default "curlimages/curl:8.11.1" | quote }}
command: ["/bin/sh", "-c"]
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
