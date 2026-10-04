#!/bin/sh
#
# The extended Pi adapter's entrypoint.
#
# Derived from the upstream Pi adapter's entrypoint.sh, which is the reference for
# this contract. The deltas are deliberate and few:
#
#   * `--no-skills` is dropped, so Pi can read the authoring skills in the image.
#   * `--no-tools` is dropped, so Pi can write a composition and run the engine.
#   * the toolchain is put on PATH and the agent is told where its skills live.
#
# Everything else — the contract check, the credential checks, the provider
# config, the result protocol, the bounded output — is upstream's, unchanged, so
# the platform sees exactly the behaviour it expects.
set -eu

result_path="${SYMPOZIUM_RESULT_PATH:-/ipc/output/result.json}"
work_path="${TMPDIR:-/tmp}/pi-output.txt"

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

# The browser must be findable and run headless as a non-root user under a
# read-only root filesystem. Chrome writes its profile under $HOME, which the
# platform mounts writable; /tmp is the scratch space a render needs.
export CHROME_BIN="${CHROME_BIN:-/usr/bin/chromium-browser}"
[ -x "$CHROME_BIN" ] || CHROME_BIN="$(command -v chromium chromium-browser 2>/dev/null | head -1 || true)"
[ -n "$CHROME_BIN" ] || fail "no chromium in the image"
export HYPERFRAMES_BROWSER_PATH="$CHROME_BIN"
export HYPERFRAMES_SKIP_SKILLS=1

mkdir -p "$HOME/.pi/agent"
jq -n \
  --arg base_url "$MODEL_BASE_URL" \
  --arg model "$MODEL_NAME" \
  '{providers:{sympozium:{baseUrl:$base_url,api:"openai-completions",apiKey:"$OPENAI_API_KEY",compat:{supportsDeveloperRole:false,supportsReasoningEffort:false},models:[{id:$model,reasoning:false,input:["text"],contextWindow:65536,maxTokens:8192}]}}}' \
  > "$HOME/.pi/agent/models.json"

# The task is the brief, and the agent is told what it has: the engine, its
# skills, and the gate it must pass. Kept short and literal — this is a prompt
# for a small model, and prose it cannot act on is prompt budget wasted.
PROMPT="$(cat <<TASK
${TASK}

You are authoring a HyperFrames video composition, not answering in prose.

Working directory: $PWD (write index.html here; it is a persisted volume).
Engine: hyperframes, on PATH. Skills: /opt/hyperframes/skills/ — read
hyperframes/SKILL.md first, and hyperframes-cli/SKILL.md for the lint and render
commands.
A vendored GSAP is at /opt/hyperframes/vendor/gsap.min.js. Never reference a CDN;
the render is offline.

The composition contract this engine enforces, in short:
- one root element carrying data-composition-id, data-start, data-duration,
  data-width and data-height; the id must match the timeline key below;
- one paused timeline: gsap.timeline({paused:true}) registered at
  window.__timelines["<the root's data-composition-id>"];
- timed elements carry class="clip" plus data-start and data-duration, and the
  runtime owns their visibility - never tween visibility or autoAlpha on a .clip,
  animate a child instead;
- never pair a CSS transform with a GSAP tween on the same property; set the
  start state inside the tween;
- no network at render time.

Do this in order, and do not skip the gate:
1. Write index.html.
2. Run: hyperframes lint
3. Fix every error it reports. Re-run lint until it reports 0 errors.
4. Run: hyperframes render -o out.mp4 -f 30
5. Report what you produced: the file paths, and the duration and frame count
   that ffprobe gives for out.mp4.

If a step fails twice with the same error, report the error verbatim rather than
guessing again.
TASK
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
