# Deploying the session path

The objects that produced `agents/render-samples/pi-authored/` — a composition
authored and rendered by a `pi` agent in-cluster, with nobody in the loop. They are
here rather than in a scratch directory because a session is not reproducible from the
image alone: it needs the policy, the runtime, the agent and the session, in that order.

```
kubectl apply -f session.yaml            # policy, runtime, agent, session
kubectl apply -f session-model-egress.yaml   # only if your gateway is not on 443/8080/9473
```

## Why a session, and not an AgentRun

`internal/controller/agentrun_controller.go` hardcodes a Job's `agent` container to
**1 GiB** and no CRD field reaches it — a sweep of every Sympozium CRD found nothing.
Eight authoring runs were OOMKilled there.

`internal/controller/harnesssession_controller.go` reads the field:

```go
Resources: corev1.ResourceRequirements{},
...
if runtime.Spec.Resources != nil {
    container.Resources = *runtime.Spec.Resources
}
```

So `contractVersion: v1alpha2` plus `spec.session` is what makes the memory ours to
set. That is the entire reason `session.yaml` exists.

## The order matters

The controller refuses a session whose runtime is not `Ready`, and a runtime whose
image policy does not admit it. So:

1. **`SympoziumPolicy`** — `harnessPolicy.enabled: true` (harness mode is denied by
   default), and the image's **full digest** in `imagePolicy.allowedRegistries`. That
   list is matched by **string prefix**, so a bare `ghcr.io/datahub-local` would admit
   every repository under the org.
2. **`AgentRuntime`** — the digest, `contractVersion: v1alpha2`, a
   `session: {protocol: openai-chat, port: 8080}` block, `capabilities`, and the
   `resources` this path exists for.
3. **`Agent`** — `policyRef`, `runtimeRef`, `authRefs`.
4. **`HarnessSession`** — `agentRef`, `runtimeRef`, `desiredState: running`.

## The two things that will bite on a fresh session

**The PVC is 1 GiB and the engine refuses to render below 1024 MiB.** The controller
hardcodes `harnessSessionStateClaimSize = "1Gi"` — 974 MiB — and `checkDisk()` in
HyperFrames errors on `freeMb < 1024`. That is 50 MiB short and structurally
impossible to satisfy, so a new session cannot render until its volume grows:

```
kubectl -n automation patch pvc <session-name> --type=merge \
  -p '{"spec":{"resources":{"requests":{"storage":"8Gi"}}}}'
kubectl -n automation rollout restart deploy/<session-name>
```

The controller sizes a claim **only at creation** (`if claim.CreationTimestamp.IsZero()`),
so it will not fight the change — its own comment says an operator who expanded the
volume is not overruled. The restart is what completes the filesystem resize:
Longhorn reports `FileSystemResizePending` until a new pod mounts it.

**The gateway may be on a port the session cannot reach.** The session's NetworkPolicy
hardcodes its egress allowlist to `{53, 443, 8080, 9473}` with no field to extend it.
This cluster's LiteLLM gateway listens on **4000**, so a session cannot reach a
cluster-local model without `session-model-egress.yaml`. NetworkPolicies are additive,
which is why a second one works rather than replacing the controller's.

## Driving it

The session's NetworkPolicy admits **only the Sympozium apiserver** on 8080 — deliberate,
matching the docs ("the browser never receives a pod IP"). A `curl` from an unrelated
pod fails even when everything is healthy. Two ways in:

- **Through the Sympozium apiserver**, which is the supported route.
- **From inside the pod**, which is how the sample was produced:

```
POD=$(kubectl -n automation get pods -o name | grep <session-name> | head -1 | sed 's|pod/||')
kubectl -n automation exec "$POD" -c harness -- node -e '
fetch("http://127.0.0.1:8080/v1/chat/completions", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ messages: [{ role: "user", content: "<your brief>" }], session_id: "demo1" })
}).then(r => r.text()).then(t => console.log(t.slice(0, 400)))'
```

A turn takes minutes — the agent writes a composition, runs `lint`, reads the findings,
corrects, runs `check`, and renders. **Do not poll it as though it had hung**; the
sample took 237 s for authoring plus a render.

## What a turn produces

Everything lands under `/tmp/aivideo` on the session PVC — **not** `/workspace`, which
is read-only in a session container. Pull the artefacts out with `kubectl cp`:

```
kubectl -n automation cp "$POD:/tmp/aivideo/out.mp4" demo.mp4 -c harness
kubectl -n automation cp "$POD:/tmp/aivideo/index.html" index.html -c harness
```
