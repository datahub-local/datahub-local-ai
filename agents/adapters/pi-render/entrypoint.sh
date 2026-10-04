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

# A run takes minutes and its only other output is Pi's own, so each stage says
# where it is. Without this a reader of `kubectl logs` sees one blob and cannot
# tell a slow model call from a stuck render. Every line is cheap and goes to
# stderr-free stdout, which is what the platform collects.
echo "--- adapter starting ---"
echo "contract:  ${SYMPOZIUM_HARNESS_CONTRACT_VERSION}"
echo "model:     ${MODEL_NAME} @ ${MODEL_BASE_URL}"
echo "workspace: $PWD"
echo "browser:   $CHROME_BIN"
echo "engine:    $(command -v hyperframes || echo MISSING) ($(hyperframes --version 2>/dev/null | head -1 || echo '?'))"
echo "pi:        $(command -v pi || echo MISSING) ($(pi --version 2>/dev/null | head -1 || echo '?'))"
echo "prompt:    $prompt_path ($(wc -c < "$prompt_path") bytes)"
echo "task:      $(printf '%s' "$TASK" | head -c 200)"

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
#
# Output goes to stdout AND the capture file. Upstream writes it to a file only,
# which makes a long run unobservable: `kubectl logs` stays empty until the process
# exits, so a run that hangs, loops or dies at minute 12 is indistinguishable from
# one that is working. `tee` costs nothing and is the difference between watching a
# run and guessing at it. The file is still what the result payload is built from,
# so the bounded-output behaviour is unchanged.
#
# The exit code has to survive the pipe, and neither `PIPESTATUS` nor `pipefail` is
# POSIX - this runs under /bin/sh, which is dash on Debian, where `${PIPESTATUS[0]}`
# is a "Bad substitution" that kills the run outright. So the status is written to a
# file by a wrapper subshell, which works in every shell.
rc_file="${TMPDIR:-/tmp}/pi-exit-code"
set +e
( pi --print --no-session --no-prompt-templates \
    --provider sympozium --model "$MODEL_NAME" "$PROMPT" 2>&1; \
  echo "$?" > "$rc_file" ) | tee "$work_path"
set -e
rc="$(cat "$rc_file" 2>/dev/null || echo 1)"
if [ "$rc" -ne 0 ]; then
  fail "Pi exited ${rc}: $(tail -c 2000 "$work_path")"
fi
response="$(cat "$work_path")"
[ -n "$response" ] || fail "Pi returned an empty response"

# Evidence the run did what it claims, written to the log where a reader looks.
# `ls` on the workspace answers "did it write" and "did it render" without a shell
# into a pod that no longer exists by the time anyone reads it.
echo "--- workspace after the run ---"
ls -la "$PWD" 2>&1 || true
if [ -f "$PWD/out.mp4" ]; then
  echo "--- out.mp4 ---"
  ffprobe -v error -select_streams v:0 \
    -show_entries stream=width,height,nb_frames,codec_name \
    -show_entries format=duration,size \
    -of default=noprint_wrappers=1 "$PWD/out.mp4" 2>&1 || true
else
  echo "no out.mp4 was produced"
fi

emit success "$response"
