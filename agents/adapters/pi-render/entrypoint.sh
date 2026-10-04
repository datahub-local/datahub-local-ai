#!/bin/sh
#
# The Pi render adapter's entrypoint.
#
# It derives from the upstream Pi adapter's entrypoint.sh, which is the reference
# for this contract. Four deltas, each deliberate:
#
#   * `--no-tools` is dropped, so Pi can write the composition and run the engine.
#   * `--no-skills` is dropped, so Pi can read the skills baked into the image.
#   * the authoring instruction is read from a prompt file, not inlined here.
#   * the toolchain is pointed at our vendored engine and browser.
#
# Everything else — the contract check, the credential checks, the provider
# config, the result protocol, the bounded output, the skip marker — is upstream's,
# unchanged, so the platform sees exactly the behaviour it expects.
set -eu

result_path="${SYMPOZIUM_RESULT_PATH:-/ipc/output/result.json}"
work_path="${TMPDIR:-/tmp}/pi-output.txt"
prompt_path="/opt/pi-render/prompts/authoring.md"

emit() {
  status="$1"
  body="$2"
  # jq --arg, never interpolation: the body is LLM output and must not be able to
  # forge a result structure.
  if [ "$status" = success ]; then
    payload="$(jq -cn --arg response "$body" '{status:"success",response:$response}')"
  else
    payload="$(jq -cn --arg error "$body" '{status:"error",error:$error}')"
  fi
  mkdir -p "$(dirname "$result_path")"
  printf '%s' "$payload" > "$result_path"
  printf '__SYMPOZIUM_RESULT__\n%s\n__SYMPOZIUM_END__\n' "$payload"
}

fail() { emit error "$1"; exit 1; }

# A preRun hook can find no work to do. Upstream's adapter checks this marker and
# so must we: it replaces agent-runner, and nothing else reads it for us.
if [ -e /ipc/control/skip ]; then
  emit skipped "$(head -c 2000 /ipc/control/skip)"
  exit 0
fi

[ "${SYMPOZIUM_HARNESS_CONTRACT_VERSION:-}" = v1alpha1 ] || fail "unsupported harness contract: ${SYMPOZIUM_HARNESS_CONTRACT_VERSION:-unset}"
[ -n "${TASK:-}" ] || fail "no task supplied"
[ -n "${MODEL_NAME:-}" ] || fail "no model supplied"
[ -n "${MODEL_BASE_URL:-}" ] || fail "no model endpoint supplied"
[ -n "${OPENAI_API_KEY:-}" ] || fail "OPENAI_API_KEY is required"
[ -r "$prompt_path" ] || fail "authoring prompt missing at $prompt_path"

# The browser must be findable and run headless as a non-root user under a
# read-only root filesystem. Chrome writes its profile under $HOME, which the
# platform mounts writable; /tmp is the scratch space a render needs.
export CHROME_BIN="${CHROME_BIN:-}"
if [ -z "$CHROME_BIN" ]; then
  CHROME_BIN="$(command -v chromium chromium-browser google-chrome 2>/dev/null | head -1 || true)"
fi
[ -n "$CHROME_BIN" ] || fail "no chromium in the image"
export HYPERFRAMES_BROWSER_PATH="$CHROME_BIN"
export HYPERFRAMES_SKIP_SKILLS=1

mkdir -p "$HOME/.pi/agent"
jq -n \
  --arg base_url "$MODEL_BASE_URL" \
  --arg model "$MODEL_NAME" \
  '{providers:{sympozium:{baseUrl:$base_url,api:"openai-completions",apiKey:"$OPENAI_API_KEY",compat:{supportsDeveloperRole:false,supportsReasoningEffort:false},models:[{id:$model,reasoning:false,input:["text"],contextWindow:65536,maxTokens:8192}]}}}' \
  > "$HOME/.pi/agent/models.json"

# The caller's task is the brief; the file supplies the method. They are joined
# here rather than in the prompt file so the file stays a reusable constant and the
# brief arrives unmodified from the platform.
PROMPT="$(cat <<EOF
${TASK}

---

Working directory: $PWD

$(cat "$prompt_path")
EOF
)"

set +e
# --no-skills and --no-tools are deliberately NOT passed: reading the skills and
# running the engine is the entire job. --no-session and --no-prompt-templates
# stay, as upstream, because neither applies to a one-shot authoring run.
pi --print --no-session --no-prompt-templates \
  --provider sympozium --model "$MODEL_NAME" "$PROMPT" >"$work_path" 2>&1
rc=$?
set -e
if [ "$rc" -ne 0 ]; then
  fail "Pi exited ${rc}: $(tail -c 2000 "$work_path")"
fi
response="$(cat "$work_path")"
[ -n "$response" ] || fail "Pi returned an empty response"

emit success "$response"
