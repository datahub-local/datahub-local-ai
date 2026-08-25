#!/usr/bin/env python3
"""Validate the Sympozium ensemble sources under projects/.

Nothing is generated from these sources into the repository: the Helm templates
assemble each Ensemble at render time, reading ``ensemble.yaml``,
``agents/*.yaml`` and ``prompts/*.md`` directly. This script is the field-level
check that Go templates cannot reasonably do.

It exists because the failure mode here is *silence*. A mistyped skill mounts
nothing, a tool allowlisted without its MCP server simply never appears, and a
toolsDeny written with the agent-facing prefix matches nothing at all. In every
case the agent still runs and still produces a confident-looking report — it just
quietly cannot do part of its job. So these are errors, not warnings.

Usage (from the repository root):

    uv sync --extra sympozium
    uv run python agents/sympozium/scripts/validate.py
"""

import pathlib
import re
import sys

import yaml

BASE = pathlib.Path(__file__).resolve().parent.parent

# SkillPacks the Sympozium chart installs into the cluster. Mirrors
# `kubectl get skillpacks -n automation`; a skill outside this set silently
# mounts nothing.
SKILLS = {
    "code-review",
    "github-gitops",
    "incident-response",
    "k8s-ops",
    "llmfit",
    "memory",
    "software-dev",
    "sre-observability",
    "subagents",
    "web-endpoint",
}

# MCPServer name -> toolsPrefix, as provisioned by datahub-local-core in
# releases/automation/templates/sympozium_mcp_servers.yaml. The prefix is what
# agent-visible tool names are built from, so it has to match exactly.
MCP_SERVERS = {
    "datahub-local-core-automation-sympozium-mcp-k8s": "k8s",
    "datahub-local-core-automation-sympozium-mcp-github": "github",
    "datahub-local-core-automation-sympozium-mcp-grafana": "grafana",
    "datahub-local-core-automation-sympozium-mcp-postgres": "pg",
    "datahub-local-core-automation-sympozium-mcp-argocd": "argocd",
    # Ours, from ../mcp/ and deployed by templates/mcpservers.yaml.
    "datahub-local-ai-mcp-homelab-facts": "facts",
}

# Tools the agent runtime provides itself, with no MCP server involved.
BUILTIN_TOOLS = {
    "delegate_to_persona",
    "execute_command",
    "fetch_url",
    "list_directory",
    "memory_search",
    "memory_store",
    "read_file",
    "send_channel_message",
    "write_file",
}

# Tools whose own server-side name really does begin with their server's
# toolsPrefix, so a toolsDeny entry that looks doubly-prefixed is correct here.
# Verified against a live tools/list call, not assumed.
PREFIX_LOOKALIKE_TOOLS = {
    "grafana": {"grafana_api_request"},
}

# Fields the Ensemble CRD schema carries a `default:` for. The API server writes
# them into the live object at admission whether or not the manifest sets them,
# and ArgoCD compares git against that live object — so an omitted value is
# permanent OutOfSync drift, not a tidy default. Every one of them is therefore
# stated in `projects/`, which is also the only place the chosen value is
# reviewable. The alternative is another `ignoreDifferences` entry in every
# Application that ships this chart, in a repository we do not own.
#
# Confirm the list after a control-plane bump:
#
#     kubectl get crd ensembles.sympozium.ai -o json \
#       | jq -r '.. | objects | select(has("default")) | .default'
#
# Values are only quoted in the error messages; the checks accept any value.
CRD_DEFAULTS = {
    "mcpServers[].timeout": 30,
    "schedule.firstTick": "immediate",
    "memory.maxSizeKB": 256,
    "sharedMemory.storageSize": "1Gi",
}

SCHEDULE_TYPES = {"heartbeat", "scheduled", "sweep"}

# Channel types the Agent CRD accepts (`ChannelSpec.Type`). A type outside this
# set is silently never connected, like every other name in this file.
CHANNEL_TYPES = {"discord", "slack", "telegram", "whatsapp"}

# Delivery levels, each backed by a file the templates substitute into the
# persona's `{{ DELIVERY }}` token. The prose lives in Markdown rather than in
# the Go template for the same reason the system prompts do: a 4B model acts on
# countable instructions, and those have to be reviewable in a diff.

# Tokens templates/ensembles.yaml substitutes into a system prompt. Anything
# else left in braces fails the render, so it is caught here with a better
# message than Helm's.
#
# {{ DELIVERY }} is the only one a persona prompt writes for itself; the rest
# appear inside the shared delivery block the templates assemble, and are
# substituted in the same pass.
PROMPT_TOKENS = (
    "{{ DELIVERY }}",
    "{{ CHANNEL }}",
    "{{ AGENT }}",
    "{{ ENSEMBLE }}",
    "{{ SCHEDULE }}",
)

# Files every channel-bound persona gets, whatever its levels: the header that
# names the agent in the message. Split out of the three verbosity files so the
# wording exists once.
FIRST_TICKS = {"immediate", "afterInterval"}

# Keys the Helm templates stamp onto a persona from the project's `defaults:`
# block when the persona does not set them itself.
DEFAULTABLE = ("provider", "model", "runTimeout", "env")

# Runner env vars the projects are allowed to set, with why each one is a
# property of the agent rather than of the cluster. Anything outside this set is
# almost certainly a cluster knob and belongs in values, so it is rejected here
# rather than shipped into every AgentRun.
#
# MAX_TOOL_ITERATIONS caps tool calls per run at 50 by default. A 4B model
# spends calls a larger one would not, and the ceiling is not a soft limit: the
# run ends `status: error`, so the postRun delivery hook never fires and the
# report is lost in silence rather than arriving short. Confirm the name against
# the runner before changing it — the value is echoed on the run's own
# `max_tool_iterations=` config line, which is the only place it is observable.
KNOWN_ENV = {
    "MAX_TOOL_ITERATIONS": "tool-call ceiling per run; the runner defaults it to 50",
}

# Keys that belong to the cluster, not the agent, and are merged in from
# release values at render time.
VALUES_ONLY_KEYS = ("enabled", "baseURL", "policyRef", "channelConfigs")

# Allowlisted tools that change something outside the cluster's read path. Only
# one persona holds any of these today, and it is the reason homelab-reviewer is
# a separate ensemble bound to no channel. Kept as a list so a second one cannot
# be added without this file noticing.
WRITE_TOOLS = {"github_add_issue_comment"}

# Tools no persona may allowlist, with why. A discovery tool that returns several
# plausible identifiers is a liability at this model size: the agent has to pick,
# and a wrong pick fails silently. `grafana_list_datasources` was allowlisted so
# the Prometheus uid would not be a hardcoded guess; the model then chose Loki's
# hex uid over the literal `prometheus` and every query returned 404, which the
# report rendered as a fleet with no metrics. The uid is pinned in the prompts
# instead — see _check_datasource_uid.
BANNED_TOOLS = {
    "grafana_list_datasources": (
        "the uid belongs in the prompt as the literal `prometheus`. Given the "
        "datasource list, the model picks Loki's hex uid and every query 404s"
    ),
}

# SkillPacks whose mounted Markdown tells the model to shell out, with what it
# says. A skill is prose competing with the persona's own prompt, and these two
# win: `sre-observability` states "Use `execute_command` for all shell commands"
# and `k8s-ops` opens "You are running inside a Kubernetes pod with full cluster
# admin access ... kubectl works out of the box". A 4B model follows that over a
# pinned tool list, and the runner *executes* the call even though it logs
# `tool policy: denied tool "execute_command"` — the deny filters schema
# registration, not dispatch. Both also carry a sidecar whose per-run RBAC is
# bound to the shared `sympozium-agent` ServiceAccount, so mounting either grants
# every persona in the namespace write access it never asked for.
SHELL_TEACHING_SKILLS = {
    "sre-observability": (
        "its prompt-query skill says \"Use `execute_command` for all shell "
        "commands\" and demonstrates `end=$(date +%s)` epoch arguments"
    ),
    "k8s-ops": (
        "its cluster-overview skill claims \"full cluster admin access\" via "
        "kubectl and mandates its own output table, which competes with the "
        "persona's required section layout"
    ),
}

# Skills a persona may not list for itself, with the values tree that owns them.
# The web endpoint is a testing surface in front of the agent rather than part of
# what the agent is, and it costs a Deployment per persona, so which ones carry
# it is a per-cluster decision that has to be readable in one place.
VALUES_ONLY_SKILLS = {"web-endpoint": "sympozium_web_endpoint"}

# Keys `templates/mcpservers.yaml` reads. Listed so a typo in the values is a
# failure rather than a silently ignored knob — the chart has no schema.
MCP_SERVER_KEYS = frozenset(
    {
        "enabled",
        "image",
        "tag",
        "imagePullPolicy",
        "project",
        "replicas",
        "resources",
        "prometheusUrl",
        "prometheusTimeoutSeconds",
        "timeout",
        "toolsPrefix",
    }
)

# The k8s tools that answer a question by listing something. A prompt naming any
# of them is sending a 4B model to guess selectors, so _check_investigation_budget
# and _check_k8s_selector_rules both key off this set.
K8S_LOOKUP_TOOLS = ("k8s_events_list", "k8s_pods_log", "k8s_resources_list")

# Metrics the prompts name that are genuinely cumulative counters, so a bare
# reading is history rather than a state and the prompt has to spell out an
# increase()/rate() window. Read off this Prometheus with the metadata API, not
# inferred from the name — `cnpg_backends_total` and `cnpg_backends_waiting_total`
# carry a `_total` suffix and are **gauges**, so the suffix decides nothing:
#
#     curl -sG http://localhost:9090/api/v1/metadata \
#       --data-urlencode metric=<name> | jq -r '.data[][0].type'
CUMULATIVE_COUNTERS = {
    "cnpg_pg_stat_archiver_failed_count",
    "redis_evicted_keys_total",
    "node_disk_io_time_seconds_total",
    "node_edac_correctable_errors_total",
    "node_edac_uncorrectable_errors_total",
    "node_pressure_cpu_waiting_seconds_total",
    "node_pressure_io_stalled_seconds_total",
    "node_pressure_memory_stalled_seconds_total",
}

DNS_1123 = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


class Fail(Exception):
    """A validation error worth failing the whole run for."""


def _rel(path):
    return path.relative_to(BASE)


def _load_yaml(path):
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise Fail(f"{_rel(path)}: expected a YAML mapping, got {type(loaded).__name__}")
    return loaded


def _defaulted(where, field, qualifier=""):
    """Message for a CRD-defaulted field left unset. See CRD_DEFAULTS."""
    return (
        f"{where}: {field} is not set{' ' + qualifier if qualifier else ''}. The CRD "
        f"defaults it to {CRD_DEFAULTS[field]!r}, so the API server writes that into "
        f"the live object and ArgoCD reports the Ensemble permanently OutOfSync "
        f"against a manifest that omits it. State the value."
    )


def _check_prompt(project, ref, field, persona_name, used):
    """Confirm a prompt reference resolves, recording the file as used."""
    path = project / ref
    if not path.is_file():
        raise Fail(f"{persona_name}: {field} points at {ref}, which does not exist")
    if path.suffix != ".md":
        raise Fail(f"{persona_name}: {field} must point at a .md file, got {ref}")
    used.add(path.resolve())
    if not path.read_text(encoding="utf-8").strip():
        raise Fail(f"{persona_name}: {ref} is empty")


def _values():
    """Parse the release values, or None when they stop being plain YAML.

    The file is a .gotmpl. It holds no Go template directives today, and the
    cross-checks that need it degrade to a warning rather than a hard failure if
    that changes — a template in the values must not start failing validation of
    the sources.
    """
    path = BASE / "values" / "default.yaml.gotmpl"
    try:
        with path.open(encoding="utf-8") as handle:
            values = yaml.safe_load(handle)
    except yaml.YAMLError:
        return None
    return values if isinstance(values, dict) else None


def _check_mcp_servers(values):
    """Cross-check `sympozium_mcp_servers` against the sibling `agents/mcp/` tree.

    This is the one check neither Helm nor the API server can do. Helm's `.Files`
    cannot read above the chart directory, so the template cannot see whether
    `projects/<project>/` exists; the API server validates the MCPServer object
    happily either way. A wrong project name therefore deploys cleanly and the
    pod crash-loops on `no such project`, which from an agent's side looks like
    the tools simply not existing — the same silent shape as core's `mcp-k8s`
    404ing for three days behind a `status.ready: true`.

    The project directory is derived the way the template derives it: the server
    name with hyphens turned into underscores, because Kubernetes object names
    must be DNS-1123 while a Python package cannot hold a hyphen.
    """
    servers = values.get("sympozium_mcp_servers") or {}
    if not servers:
        return
    projects_dir = BASE.parent / "mcp" / "projects"
    for name, server in sorted(servers.items()):
        if not isinstance(server, dict):
            raise Fail(f"sympozium_mcp_servers.{name} is not a mapping")
        stray = sorted(set(server) - MCP_SERVER_KEYS)
        if stray:
            raise Fail(
                f"sympozium_mcp_servers.{name} has unknown key(s) "
                f"{', '.join(stray)}. Known keys: {', '.join(sorted(MCP_SERVER_KEYS))}"
            )
        if not server.get("enabled"):
            continue
        if not server.get("image"):
            raise Fail(f"sympozium_mcp_servers.{name}: image is required when enabled")
        project = server.get("project") or name.replace("-", "_")
        if not projects_dir.is_dir():
            # The sibling sub-project is absent entirely — a checkout problem, not
            # a config error, so say which it is rather than blaming the values.
            raise Fail(
                f"sympozium_mcp_servers.{name} names project {project!r} but "
                f"{projects_dir} does not exist"
            )
        if not (projects_dir / project / "__init__.py").is_file():
            available = sorted(
                path.name for path in projects_dir.iterdir() if (path / "__init__.py").is_file()
            )
            raise Fail(
                f"sympozium_mcp_servers.{name} resolves to project {project!r}, "
                f"which is not a project in agents/mcp/projects/ "
                f"(found: {', '.join(available) or 'none'}). The server would "
                f"deploy and then crash-loop on startup, which an agent "
                f"experiences as the tools not existing."
            )


def _check_env(where, env):
    """Runner env vars must be known, and their values must be strings.

    The Ensemble CRD types `env` as map[string]string and the admission webhook
    decodes strictly, so `MAX_TOOL_ITERATIONS: 80` — an int in YAML — is rejected
    outright at apply time. Quoting it is the whole fix, and a bare number is the
    natural thing to write, so it is caught here instead of at deploy.

    The name allowlist exists for the usual reason in this file: an env var the
    runner does not read is applied cleanly, changes nothing, and leaves a
    comment in the repository claiming otherwise.
    """
    if env is None:
        return
    if not isinstance(env, dict):
        raise Fail(f"{where}: env must be a mapping of name to string value")
    for key, value in sorted(env.items()):
        if key not in KNOWN_ENV:
            raise Fail(
                f"{where}: env sets {key!r}, which the runner does not read. "
                f"Known: {', '.join(sorted(KNOWN_ENV))}. An env var nothing "
                f"reads applies cleanly and changes nothing."
            )
        if not isinstance(value, str):
            raise Fail(
                f"{where}: env[{key}] is {type(value).__name__} {value!r}, not a "
                f"string. The CRD types env as map[string]string and the webhook "
                f"decodes strictly, so an unquoted number is rejected at apply "
                f"time. Write it as {str(value)!r}."
            )


def _web_endpoint_config(ensemble_name):
    """Web endpoint knobs for one ensemble: enabled, rate limits, personas.

    Returns the ensemble's own entry with the master switch already folded in, so
    callers do not each have to remember the AND.
    """
    values = _values()
    if values is None:
        return None
    root = values.get("sympozium_web_endpoint") or {}
    entry = (root.get("ensembles") or {}).get(ensemble_name) or {}
    if not isinstance(entry, dict):
        return {}
    if not root.get("enabled"):
        entry = dict(entry, enabled=False, personas={})
    return entry


def _delivery_config(ensemble_name):
    """Delivery knobs for one ensemble: channel, verbosity, notify, personas."""
    values = _values()
    if values is None:
        return None
    entry = (values.get("sympozium_delivery") or {}).get(ensemble_name) or {}
    return entry if isinstance(entry, dict) else {}


def _check_delivery(project, persona_name, persona, delivery, warnings):
    """Cross-check the delivery knobs against the persona and its prompt.

    Delivery is the one setting split across three files — the binding on the
    persona, the knobs in values, the wording in prompts/ — so every way of
    getting it half-right deploys cleanly and posts nothing, or posts the wrong
    thing to nowhere. Each check below is one of those.
    """
    if delivery is None:
        return  # values are not plain YAML; _check_channels already warned

    per_persona = delivery.get("personas") or {}
    override = per_persona.get(persona_name) or {}

    channel = override.get("channel") or delivery.get("channel")
    mode = _delivery_mode(persona_name, delivery)

    prompt = (project / persona["systemPromptFile"]).read_text(encoding="utf-8")

    if mode == "reply":
        if "{{ DELIVERY }}" in prompt:
            raise Fail(
                f"{persona_name}: deliveryMode reply substitutes no delivery "
                f"block, so its prompt must carry its own answering contract "
                f"rather than a {{{{ DELIVERY }}}} token"
            )
        if not persona.get("channels"):
            raise Fail(
                f"{persona_name}: deliveryMode reply answers in the asking "
                f"thread, so the persona must carry a channel binding"
            )
        return

    # Gated on the delivery destination and not on `channels:`. The templates
    # substitute the token for any persona with a sympozium_delivery channel,
    # while a binding is a separate decision that adds a sidecar and the
    # inbound path.
    delivers = bool(channel)

    if not delivers:
        for token in PROMPT_TOKENS:
            if token in prompt:
                raise Fail(
                    f"{persona_name}: its system prompt holds {token}, but "
                    f"neither the ensemble nor its persona override sets "
                    f"sympozium_delivery.channel, so nothing substitutes it and "
                    f"the render fails"
                )
        if override:
            warnings.append(
                f"{persona_name}: has sympozium_delivery overrides but no "
                f"channel to deliver to, so they do nothing"
            )
        return

    if "{{ DELIVERY }}" not in prompt:
        raise Fail(
            f"{persona_name}: has a delivery channel, but its system prompt has "
            f"no {{{{ DELIVERY }}}} token, so no delivery rule ever reaches the "
            f"model — under a hook it will not know its reply is the report, and "
            f"will end the run on a tool call with nothing to deliver"
        )


def _delivery_mode(persona_name, delivery):
    """hook or reply, resolved the way templates/ensembles.yaml resolves it.

    "hook" is a lifecycle.postRun container posting the run's own result, which
    touches no shared subject and so arrives exactly once whatever else exists.
    "reply" is a bound persona answering in the thread that asked, through the
    channel sidecar: no hook, no configured destination, and its own answering
    contract in its prompt instead of a substituted delivery block.
    """
    if not delivery:
        return "hook"
    override = (delivery.get("personas") or {}).get(persona_name) or {}
    return str(
        override.get("deliveryMode") or delivery.get("deliveryMode") or "hook"
    ).lower()


def _check_delivery_needs_binding(personas, delivery, warnings):
    """A persona that delivers must carry the `channels:` binding for its type.

    Verified on the cluster 2026-08-23, because the shape of this coupling is not
    guessable and getting it wrong is silent both ways.

    `send_channel_message` is registered on *any* persona, bound or not — a probe
    run of the unbound `renovate-reviewer` called it, got an answer, and reported
    `Succeeded` with result `DONE`. The message still never left the pod:

        ipc-bridge  Dropping outbound message to channel not configured on this
                    agent  path=/ipc/messages/send-….json  channel=slack

    So the binding is what lets an outbound message reach the event bus at all,
    and delivery cannot be separated from it. That matters because the binding
    also deploys a channel sidecar, and every sidecar of a transport delivers
    *every* instance's message — it filters on `data.channel` and never on the
    `metadata.instanceName` it is handed. Each delivering persona therefore costs
    one duplicate copy of every report in the ensemble, and there is no way to
    have one without the other from here. The upstream fix is a one-line filter on
    metadata.instanceName in the channel sidecar. Written up in
    MEMORY.md#every-report-arrived-five-times-and-only-one-agent-sent-it

    The tempting workaround — unbind all but one persona and let its sidecar carry
    the ensemble — was tried and does not work. It is what the probe above was
    testing. Those four personas go completely silent, with every run still
    reporting `Succeeded`.
    """
    if not delivery:
        return
    for name, persona in personas:
        override = (delivery.get("personas") or {}).get(name) or {}
        if not (override.get("channel") or delivery.get("channel")):
            continue
        mode = _delivery_mode(name, delivery)
        if mode not in ("tool", "hook"):
            raise Fail(f"{name}: deliveryMode {mode!r} is neither tool nor hook")
        if mode == "hook":
            # A postRun hook posts straight to the Slack API and never reaches
            # the event bus, so it needs no binding. Any binding left on a
            # hook-mode persona is purely the inbound @-mention path.
            per = (delivery.get("personas") or {}).get(name) or {}
            for knob, why in (
                (
                    "notify",
                    (
                        "a hook posts every run unconditionally, so this would "
                        "claim a suppression that does not happen — stretch "
                        "schedule.interval instead"
                    ),
                ),
                (
                    "verbosity",
                    (
                        "the verbosity files describe how to call the posting "
                        "tool; hook mode substitutes prompts/delivery/hook.md "
                        "instead and never reads them"
                    ),
                ),
            ):
                if per.get(knob) or delivery.get(knob):
                    raise Fail(
                        f"{name}: deliveryMode is hook but {knob} is set — {why}"
                    )
            if not (BASE / "prompts" / "delivery" / "hook.md").is_file():
                raise Fail(
                    f"{name}: deliveryMode is hook but prompts/delivery/hook.md "
                    f"is missing, so nothing would tell the model that its reply "
                    f"is the report and it would end the run with no final text"
                )
            if "send_channel_message" in persona.get("toolPolicy", {}).get("allow", []):
                raise Fail(
                    f"{name}: deliveryMode is hook but it still allowlists "
                    f"'send_channel_message'. Then the model both posts and is "
                    f"posted for, so the report arrives twice — and worse, the "
                    f"run ends on a tool call, which is what leaves "
                    f"status.result empty and gives the hook nothing to send"
                )
            continue
        if not (persona.get("channels") or []):
            raise Fail(
                f"{name}: sympozium_delivery gives it a channel to post to, but "
                f"the persona has no `channels:` binding. The ipc-bridge drops "
                f"an outbound message from an agent with no channel configured "
                f"('Dropping outbound message to channel not configured on this "
                f"agent'), so every run would succeed and post nothing. Add "
                f"`channels: [slack]` — and note it costs one duplicate copy of "
                f"every report in this ensemble, which is an upstream bug this "
                f"repo cannot fix. Prefer deliveryMode: hook."
            )

    bound = [n for n, p in personas if p.get("channels")]
    tool_mode = [
        n for n, p in personas
        if _delivers(n, p, delivery) and _delivery_mode(n, delivery) == "tool"
    ]
    if len(bound) > 1 and tool_mode:
        warnings.append(
            f"{len(bound)} personas are channel-bound, so every report still on "
            f"deliveryMode: tool ({', '.join(sorted(tool_mode))}) arrives "
            f"{len(bound)} times — each channel sidecar delivers every "
            f"instance's message. Move them to deliveryMode: hook; see "
            f"MEMORY.md#every-report-arrived-five-times-and-only-one-agent-sent-it"
        )


def _delivers(persona_name, persona, delivery):
    """Whether a sympozium_delivery destination resolves for this persona."""
    if not delivery:
        return False
    override = (delivery.get("personas") or {}).get(persona_name) or {}
    return bool(override.get("channel") or delivery.get("channel"))


def _check_unknown_delivery_personas(ensemble_name, persona_names):
    """A typo under `personas:` silently leaves that agent on the defaults."""
    delivery = _delivery_config(ensemble_name)
    if not delivery:
        return
    unknown = sorted(set(delivery.get("personas") or {}) - set(persona_names))
    if unknown:
        raise Fail(
            f"sympozium_delivery.{ensemble_name}.personas names "
            f"{', '.join(unknown)}, which is not a persona in this ensemble"
        )


def _channel_secrets(ensemble_name):
    """Read spec.channelConfigs for one ensemble out of the release values.

    A channel binding needs two halves that live in different files: the type on
    the persona (`channels: [slack]`, in projects/) and the secret holding that
    type's credentials (`channelConfigs: {slack: ...}`, in values/, because a
    secret name describes the cluster). Miss the second half and the controller
    has no ConfigRef to set — the agent deploys, connects to nothing, and its
    report goes nowhere, which is the exact failure this script exists to catch.

    The values file is a .gotmpl. It is plain YAML today, and the cross-check is
    skipped with a warning rather than a hard failure if that ever stops being
    true — a Go template in it must not start failing validation of the sources.
    """
    values = _values()
    if values is None:
        return None
    ensembles = values.get("sympozium_ensembles") or {}
    entry = ensembles.get(ensemble_name) or {}
    configs = entry.get("channelConfigs")
    return configs if isinstance(configs, dict) else {}


def _check_channels(persona_name, persona, channel_secrets, warnings, hook_mode=False):
    """Cross-check channel bindings, their credentials, and the posting tool.

    Three ways to bind a channel and still be silent, all of which deploy
    cleanly: a type with no `channelConfigs` entry (nothing to authenticate
    with), `send_channel_message` allowlisted with no channel to send to, and
    slackOptions on a persona that is not on Slack.
    """
    channels = persona.get("channels") or []
    if not isinstance(channels, list):
        raise Fail(f"{persona_name}: channels must be a list of channel types")

    unknown = sorted(set(channels) - CHANNEL_TYPES)
    if unknown:
        raise Fail(
            f"{persona_name}: unknown channel type(s) {', '.join(unknown)}. "
            f"The CRD accepts: {', '.join(sorted(CHANNEL_TYPES))}"
        )

    if channel_secrets is None:
        if channels:
            warnings.append(
                f"{persona_name}: values/default.yaml.gotmpl is no longer plain "
                f"YAML, so channelConfigs could not be cross-checked"
            )
    else:
        for channel in channels:
            if not channel_secrets.get(channel):
                raise Fail(
                    f"{persona_name}: bound to the {channel!r} channel, but the "
                    f"ensemble has no channelConfigs.{channel} in "
                    f"values/default.yaml.gotmpl, so the controller has no "
                    f"credential secret to reference and the binding connects "
                    f"to nothing"
                )

    allowed = persona.get("toolPolicy", {}).get("allow", [])
    if "send_channel_message" in allowed and not channels:
        raise Fail(
            f"{persona_name}: allowlists 'send_channel_message' but is bound to "
            f"no channel. The tool is still registered and still answers on an "
            f"unbound agent — verified — but the ipc-bridge drops the message "
            f"before the event bus ('Dropping outbound message to channel not "
            f"configured on this agent'), so the run succeeds and posts nothing. "
            f"Binding is not optional for delivery; see _check_delivery_needs_binding"
        )
    if channels and "send_channel_message" not in allowed and not hook_mode:
        warnings.append(
            f"{persona_name}: bound to {', '.join(channels)} but does not "
            f"allowlist 'send_channel_message' — it can be triggered from the "
            f"channel but cannot report back to it"
        )
    if persona.get("slackOptions") and "slack" not in channels:
        raise Fail(f"{persona_name}: sets slackOptions but is not bound to the slack channel")


def _check_tools(persona_name, persona, warnings):
    """Cross-check the tool allowlist against the MCP servers actually wired.

    The trap this catches outright is an allowlisted tool whose server was never
    attached to the persona — the tool then simply never appears, and the agent
    quietly works without it.

    A toolsDeny entry carrying the agent-facing prefix is only a warning, not an
    error: it is usually the bug that core's own MCPServer catalog has (a deny
    that matches nothing), but some servers genuinely name their own tools that
    way — the Grafana server really does expose `grafana_api_request`.
    """
    wired = {}
    for server in persona.get("mcpServers", []):
        name = server.get("name")
        prefix = server.get("toolsPrefix")
        if name not in MCP_SERVERS:
            raise Fail(f"{persona_name}: unknown MCP server {name!r}")
        if prefix != MCP_SERVERS[name]:
            raise Fail(
                f"{persona_name}: MCP server {name!r} has toolsPrefix {prefix!r}, "
                f"but the cluster catalog provisions it as {MCP_SERVERS[name]!r}"
            )
        if server.get("timeout") is None:
            raise Fail(_defaulted(persona_name, "mcpServers[].timeout", f"on {name!r}"))
        wired[prefix] = name
        lookalikes = PREFIX_LOOKALIKE_TOOLS.get(prefix, set())
        for denied in server.get("toolsDeny", []):
            if denied.startswith(f"{prefix}_") and denied not in lookalikes:
                warnings.append(
                    f"{persona_name}: toolsDeny entry {denied!r} on {prefix!r} looks "
                    f"prefixed. toolsDeny takes the server's own tool names, "
                    f"unprefixed — unless the server really does call it that, this "
                    f"deny matches nothing and should read {denied[len(prefix) + 1:]!r}"
                )

    policy = persona.get("toolPolicy", {})

    for tool in policy.get("allow", []):
        if tool in BANNED_TOOLS:
            raise Fail(
                f"{persona_name}: toolPolicy.allow lists {tool!r}, which no "
                f"persona may hold — {BANNED_TOOLS[tool]}"
            )

    # toolsAllow is the only knob that bounds the *prompt*, as opposed to what
    # the agent is permitted to do. toolPolicy filters at the LLM request, but
    # every tool the server exposes is still registered and its schema still
    # injected: the grafana catalogue is 66 tools and costs ~40k prompt tokens,
    # which overflowed the window outright before it was raised to 65536 and is
    # still most of it. So each
    # wired server must pin toolsAllow to exactly the tools this persona
    # allowlists, unprefixed.
    for server in persona.get("mcpServers", []):
        prefix = server.get("toolsPrefix")
        wanted = sorted(
            tool[len(prefix) + 1:]
            for tool in policy.get("allow", [])
            if tool.startswith(f"{prefix}_")
        )
        declared = server.get("toolsAllow")
        if declared is None:
            raise Fail(
                f"{persona_name}: MCP server {prefix!r} has no toolsAllow. Without "
                f"it every tool the server exposes is registered and its schema "
                f"injected into the context window — the grafana catalogue alone "
                f"is 66 tools and ~40k prompt tokens, most of the window, spent "
                f"before the run reads its task. Pin it to: {', '.join(wanted)}"
            )
        if sorted(declared) != wanted:
            raise Fail(
                f"{persona_name}: MCP server {prefix!r} toolsAllow does not match "
                f"toolPolicy.allow. toolsAllow has {sorted(declared)}, "
                f"toolPolicy.allow implies {wanted}. A tool in toolsAllow but not "
                f"toolPolicy.allow is prompt weight the model may never use; one "
                f"in toolPolicy.allow but not toolsAllow never reaches the agent "
                f"at all."
            )

    for tool in policy.get("allow", []) + policy.get("deny", []):
        if tool in BUILTIN_TOOLS:
            continue
        prefix = tool.split("_", 1)[0]
        if prefix not in MCP_SERVERS.values():
            raise Fail(
                f"{persona_name}: {tool!r} is neither a built-in tool nor "
                f"prefixed with a known MCP server prefix "
                f"({', '.join(sorted(set(MCP_SERVERS.values())))})"
            )
        if prefix not in wired:
            raise Fail(
                f"{persona_name}: toolPolicy references {tool!r}, but no "
                f"{prefix!r} MCP server is wired on this persona"
            )


def _check_schedule(persona_name, schedule):
    kind = schedule.get("type")
    if kind not in SCHEDULE_TYPES:
        raise Fail(
            f"{persona_name}: schedule.type {kind!r} is not one of "
            f"{', '.join(sorted(SCHEDULE_TYPES))}"
        )
    if "cron" not in schedule and "interval" not in schedule:
        raise Fail(f"{persona_name}: schedule needs either cron or interval")
    if "cron" in schedule and "interval" in schedule:
        raise Fail(f"{persona_name}: schedule sets both cron and interval — pick one")
    first_tick = schedule.get("firstTick")
    if first_tick is None:
        raise Fail(_defaulted(persona_name, "schedule.firstTick"))
    if first_tick not in FIRST_TICKS:
        raise Fail(
            f"{persona_name}: schedule.firstTick {first_tick!r} is not one of "
            f"{', '.join(sorted(FIRST_TICKS))}"
        )


def _check_persona(project, path, used, channel_secrets, delivery, warnings):
    persona = _load_yaml(path)
    name = persona.get("name")
    if not name:
        raise Fail(f"{_rel(path)}: missing name")
    if not DNS_1123.match(name):
        raise Fail(f"{_rel(path)}: name {name!r} is not a valid DNS-1123 label")
    if name != path.stem:
        raise Fail(f"{_rel(path)}: name {name!r} does not match the file name")
    if not persona.get("displayName"):
        raise Fail(f"{name}: missing displayName")

    if "systemPrompt" in persona:
        raise Fail(
            f"{name}: systemPrompt is inlined. Prompts live in prompts/*.md and "
            f"are referenced with systemPromptFile, so they stay reviewable."
        )
    ref = persona.get("systemPromptFile")
    if not ref:
        raise Fail(f"{name}: missing systemPromptFile")
    _check_prompt(project, ref, "systemPromptFile", name, used)

    skills = persona.get("skills") or []
    unknown = sorted(set(skills) - SKILLS)
    if unknown:
        raise Fail(
            f"{name}: unknown skill(s) {', '.join(unknown)}. Installed SkillPacks: "
            f"{', '.join(sorted(SKILLS))}"
        )
    for skill in sorted(set(skills) & set(SHELL_TEACHING_SKILLS)):
        raise Fail(
            f"{name}: lists the {skill!r} skill, which teaches the model to "
            f"shell out — {SHELL_TEACHING_SKILLS[skill]}. The tools this "
            f"persona may use are its toolPolicy allowlist and nothing else; "
            f"the skill overrides that in prose and the runner honours it."
        )

    memory = persona.get("memory")
    if memory is not None and memory.get("maxSizeKB") is None:
        raise Fail(_defaulted(name, "memory.maxSizeKB"))

    schedule = persona.get("schedule")
    if schedule is not None:
        if "task" in schedule:
            raise Fail(f"{name}: schedule.task is inlined — use schedule.taskFile")
        task_ref = schedule.get("taskFile")
        if not task_ref:
            raise Fail(f"{name}: schedule is set but schedule.taskFile is missing")
        _check_prompt(project, task_ref, "schedule.taskFile", name, used)
        _check_schedule(name, schedule)

    _check_env(name, persona.get("env"))
    _check_tools(name, persona, warnings)
    _check_channels(
        name, persona, channel_secrets, warnings,
        hook_mode=_delivery_mode(name, delivery) == "hook",
    )
    _check_delivery(project, name, persona, delivery, warnings)
    return name


def check(project):
    """Validate one project directory. Returns (persona names, warnings)."""
    source = _load_yaml(project / "ensemble.yaml")
    name = source.get("name")
    if not name:
        raise Fail("ensemble.yaml: missing name")
    if name != project.name:
        raise Fail(f"ensemble.yaml: name {name!r} does not match the directory name")
    if not DNS_1123.match(name):
        raise Fail(f"{name}: not a valid DNS-1123 label")

    spec = source.get("spec") or {}
    for forbidden in VALUES_ONLY_KEYS + ("agentConfigs",):
        if forbidden in spec:
            raise Fail(
                f"spec.{forbidden} does not belong in ensemble.yaml "
                f"(per-cluster knobs live in values/default.yaml.gotmpl, "
                f"personas in agents/)"
            )

    shared_memory = spec.get("sharedMemory")
    if shared_memory is not None and shared_memory.get("storageSize") is None:
        raise Fail(_defaulted("ensemble.yaml", "sharedMemory.storageSize"))

    _check_env("ensemble.yaml defaults", (source.get("defaults") or {}).get("env"))

    unknown_defaults = sorted(set(source.get("defaults") or {}) - set(DEFAULTABLE))
    if unknown_defaults:
        raise Fail(
            f"defaults contains {', '.join(unknown_defaults)}, which the templates "
            f"do not stamp onto personas. Supported: {', '.join(DEFAULTABLE)}"
        )

    agents_dir = project / "agents"
    persona_files = sorted(agents_dir.glob("*.yaml"))
    if not persona_files:
        raise Fail(f"no personas found in {_rel(agents_dir)}")

    used = set()
    warnings = []
    channel_secrets = _channel_secrets(name)
    delivery = _delivery_config(name)
    names = [
        _check_persona(project, path, used, channel_secrets, delivery, warnings)
        for path in persona_files
    ]
    _check_delivery_needs_binding(
        [
            (path.stem, yaml.safe_load(path.read_text(encoding="utf-8")) or {})
            for path in persona_files
        ],
        delivery,
        warnings,
    )
    _check_unknown_delivery_personas(name, names)

    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise Fail(f"duplicate persona name(s) {', '.join(duplicates)}")

    orphans = sorted(
        _rel(path).as_posix()
        for path in (project / "prompts").glob("*.md")
        if path.resolve() not in used
    )
    if orphans:
        raise Fail(
            f"prompt file(s) referenced by no persona: {', '.join(orphans)}. "
            f"Delete them or wire them up."
        )

    return names, warnings


def main():
    projects = sorted(
        path for path in (BASE / "projects").iterdir() if (path / "ensemble.yaml").is_file()
    )
    if not projects:
        print("no projects found", file=sys.stderr)
        return 1

    values = _values() or {}
    try:
        _check_mcp_servers(values)
    except Fail as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    known = {path.name for path in projects}
    for tree, entries in (
        ("sympozium_delivery", values.get("sympozium_delivery") or {}),
    ):
        unknown = sorted(set(entries) - known)
        if unknown:
            print(
                f"error: {tree} names ensemble(s) that do not exist: "
                f"{', '.join(unknown)}",
                file=sys.stderr,
            )
            return 1

    failed = False
    for project in projects:
        try:
            names, warnings = check(project)
        except Fail as error:
            print(f"error: {project.name}: {error}", file=sys.stderr)
            failed = True
            continue
        for warning in warnings:
            print(f"warning: {project.name}: {warning}", file=sys.stderr)
        print(f"projects/{project.name}: {len(names)} personas OK ({', '.join(names)})")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
