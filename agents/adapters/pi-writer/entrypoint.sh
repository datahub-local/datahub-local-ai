#!/bin/sh
#
# The Pi writer adapter's entrypoint.
#
# It derives from the maintained Pi adapter's entrypoint.sh, which is the reference
# for this contract. The deltas are the writer's own:
#
#   * `--no-tools` is dropped, so Pi can fetch the cited pages and render a manifest.
#   * the writing instruction is read from a prompt file, not inlined here.
#   * this adapter serves sessions only. An article needs the session directory and
#     the serialized turn a `HarnessSession` provides; a one-shot Job has neither, so
#     an AgentRun gets a named refusal rather than a half-working turn.
#
# Everything else — the contract check, the credential checks, the provider config,
# the result protocol, the skip marker — is upstream's shape, so the platform sees
# the behaviour it expects.
set -eu

# v1alpha2 is the session contract: a long-lived Deployment that serves
# /v1/chat/completions. Dispatch before anything below assumes the Job contract —
# the session container mounts no /ipc, so the result protocol would crash on a
# read-only root filesystem trying to create one.
if [ "${SYMPOZIUM_HARNESS_CONTRACT_VERSION:-}" = v1alpha2 ]; then
  exec node /usr/local/bin/sympozium-pi-writer-session
fi

result_path="${SYMPOZIUM_RESULT_PATH:-/ipc/output/result.json}"

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
  # A Job mounts /ipc writable; anything else may not, and a failure to write the
  # result must still leave the reason readable on stdout rather than dying on an
  # mkdir. The marker goes out either way.
  if mkdir -p "$(dirname "$result_path")" 2>/dev/null; then
    printf '%s' "$payload" > "$result_path" 2>/dev/null || \
      echo "sympozium pi writer adapter: could not write $result_path" >&2
  else
    echo "sympozium pi writer adapter: could not create $(dirname "$result_path")" >&2
  fi
  printf '__SYMPOZIUM_RESULT__\n%s\n__SYMPOZIUM_END__\n' "$payload"
}

emit error "the pi-writer adapter serves v1alpha2 sessions only; got contract ${SYMPOZIUM_HARNESS_CONTRACT_VERSION:-unset}"
exit 1
