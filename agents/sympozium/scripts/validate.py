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
VERBOSITY_LEVELS = {"quiet", "normal", "verbose"}
NOTIFY_LEVELS = {"always", "onchange", "never"}

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
SHARED_DELIVERY_FILES = ("delivery/header.md",)
FIRST_TICKS = {"immediate", "afterInterval"}

# Keys the Helm templates stamp onto a persona from the project's `defaults:`
# block when the persona does not set them itself.
DEFAULTABLE = ("provider", "model", "runTimeout")

# Keys that belong to the cluster, not the agent, and are merged in from
# release values at render time.
VALUES_ONLY_KEYS = ("enabled", "baseURL", "policyRef", "channelConfigs")

# Allowlisted tools that change something outside the cluster's read path. Only
# one persona holds any of these today, and it is the reason homelab-reviewer is
# a separate ensemble bound to no channel. Kept as a list so a second one cannot
# be added without this file noticing.
WRITE_TOOLS = {"github_add_issue_comment"}

# Skills a persona may not list for itself, with the values tree that owns them.
# The web endpoint is a testing surface in front of the agent rather than part of
# what the agent is, and it costs a Deployment per persona, so which ones carry
# it is a per-cluster decision that has to be readable in one place.
VALUES_ONLY_SKILLS = {"web-endpoint": "sympozium_web_endpoint"}

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


def _check_shared_prompts():
    """Check the shared delivery block: the files exist and hold known tokens only.

    These files are substituted into every channel-bound persona, so a typo in
    one of them breaks every agent at once. Helm catches an unknown token, but
    only as "still holds an unsubstituted token" against the *persona's* prompt
    file, which is not where the typo is.
    """
    root = BASE / "prompts"
    names = [f"delivery/{level}.md" for level in VERBOSITY_LEVELS]
    names += [f"notify/{level}.md" for level in NOTIFY_LEVELS]
    names += list(SHARED_DELIVERY_FILES)
    for name in names:
        path = root / name
        if not path.is_file():
            raise Fail(f"prompts/{name} is missing")
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise Fail(f"prompts/{name} is empty")
        for token in re.findall(r"\{\{.*?\}\}", text):
            if token not in PROMPT_TOKENS:
                raise Fail(
                    f"prompts/{name}: {token} is not a token the templates "
                    f"substitute. Known tokens: {', '.join(PROMPT_TOKENS)}"
                )
    header = (root / "delivery" / "header.md").read_text(encoding="utf-8")
    _check_verbatim_ascii("delivery/header.md", header)
    for token in ("{{ AGENT }}", "{{ SCHEDULE }}"):
        if token not in header:
            raise Fail(
                f"prompts/delivery/header.md no longer holds {token}. It is the "
                f"only thing that tells a reader which of six agents wrote a "
                f"report, which is the whole reason the file exists."
            )
    # Delivery has to be a completion condition of the run, not a step in the
    # task. The imperative used to live only in the persona's taskFile, and the
    # web-endpoint proxy truncates the task to its first line — so a
    # web-triggered run wrote a full CRITICAL report and never sent it, with
    # nothing failing. Any caller can supply a one-line task; the prompt has to
    # carry the requirement on its own.
    for level in NOTIFY_LEVELS - {"never"}:
        text = (root / "notify" / f"{level}.md").read_text(encoding="utf-8")
        if "send_channel_message" not in text:
            raise Fail(
                f"prompts/notify/{level}.md does not name send_channel_message as "
                f"what finishes the run. Left to the taskFile, the instruction is "
                f"lost whenever a caller supplies its own task — the web-endpoint "
                f"proxy truncates the task to one line, and the agent then writes "
                f"the report and delivers nothing, with no run failing."
            )

    for level in VERBOSITY_LEVELS:
        text = (root / "delivery" / f"{level}.md").read_text(encoding="utf-8")
        if "chatId" not in text or "{{ CHANNEL }}" not in text:
            raise Fail(
                f"prompts/delivery/{level}.md does not spell out the chatId "
                f"argument. send_channel_message takes the *transport* in "
                f"`channel` ('slack') and the destination in `chatId`; a prompt "
                f"that says only 'post to {{{{ CHANNEL }}}}' makes the model pass "
                f"the channel name as the transport, and the tool then answers "
                f"'Message sent' while delivering nothing."
            )
        _check_verbatim_ascii(f"delivery/{level}.md", text)
        _check_unquoted_args(f"prompts/delivery/{level}.md", text)
        if '"{{ CHANNEL }}"' in text or "'{{ CHANNEL }}'" in text:
            raise Fail(
                f"prompts/delivery/{level}.md shows the chatId value in quotes. "
                f"A 4B model copies the quotes into the argument, so chatId "
                f"arrives as '\"#channel\"' — a channel that does not exist, "
                f"which Slack rejects as channel_not_found while the tool still "
                f"answers 'Message sent'. Write the value bare."
            )


def _check_fill_direction(label, text):
    """A fill expression must compute the fraction *used*, not the fraction free.

    `available / capacity` is how much room is left. Reporting it as "percent
    full" inverts every finding: it flags the emptiest volumes and can never flag
    a full one. sre-sentinel shipped that mistake and spent days calling a
    2%-used volume "97.9% full, write operations failing" — CRITICAL every run,
    which also tripped the change test and forced a Slack post every time, so the
    inversion defeated the anti-noise rule as well.

    The fix is an explicit `1 -`, so that is what this checks: any line dividing
    an availability metric by a capacity metric has to invert it on the same
    line.
    """
    avail = re.compile(r"(?:_available_bytes|_avail_bytes)")
    cap = re.compile(r"(?:_capacity_bytes|_size_bytes)")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if "/" not in line:
            continue
        before, _, after = line.partition("/")
        if not (avail.search(before) and cap.search(after)):
            continue
        if "1 -" in line or "1-" in line:
            continue
        raise Fail(
            f"{label}:{lineno} divides an availability metric by a capacity "
            f"metric without inverting it. That is the fraction *free*, so "
            f"reporting it as fill flags the emptiest volumes and never a full "
            f"one — the bug that had this fleet calling a 2%-used volume "
            f"'97.9% full' on every run. Write it as "
            f"`100 * (1 - available / capacity)`."
        )


def _check_unquoted_args(label, text):
    """Argument values in a prompt's call block must be written bare.

    Same failure as the delivery prompts: a 4B model reproduces an indented
    `key: "value"` block character for character, quotes included, and the
    argument arrives with the punctuation inside it. That cost every Slack report
    for two days when it happened to `chatId`; `queryType: "instant"` is the same
    shape and would fail the same way, silently, as an unparseable query type.

    Deliberately narrow: it checks only the argument names of the two call
    contracts the prompts spell out. PromQL in an indented block legitimately
    contains quotes (`ALERTS{alertstate="firing"}`), so a blanket rule would be
    wrong.
    """
    args = ("datasourceUid", "queryType", "endTime", "chatId", "channel")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.startswith("    "):
            continue
        stripped = line.strip()
        for arg in args:
            if not stripped.startswith(arg):
                continue
            value = stripped[len(arg):].lstrip(": ").strip()
            if value.startswith(('"', "'")):
                raise Fail(
                    f"{label}:{lineno} shows the {arg!r} argument value "
                    f"in quotes. A 4B model copies the quotes into the argument "
                    f"— that is how chatId became '\"#channel\"' and every "
                    f"report stopped arriving. Write the value bare."
                )


def _check_verbatim_ascii(label, text):
    """Indented blocks in the delivery prompts must be pure ASCII.

    These blocks are the strings the model is ordered to reproduce character for
    character — the report header above all. A 4B model reproducing a multi-byte
    character sometimes emits a broken sequence, and the runner ships its final
    reply to the controller over gRPC, which refuses to marshal a string that is
    not valid UTF-8:

        rpc error: ... grpc: error while marshaling: string field contains
        invalid UTF-8

    The run still reports Succeeded, the report still reaches Slack, and
    status.result is silently empty — which is what the run page then shows. The
    header used U+00B7 as its separator and roughly 58% of runs came back with no
    result at all. Keep every character the model must echo inside ASCII.
    """
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.startswith("    "):
            continue
        bad = sorted({ch for ch in line if not (" " <= ch <= "~")})
        if bad:
            shown = ", ".join(f"{ch!r} (U+{ord(ch):04X})" for ch in bad)
            raise Fail(
                f"prompts/{label}:{lineno} has non-ASCII in an indented block "
                f"the model is told to reproduce verbatim: {shown}. A 4B model "
                f"mangles multi-byte characters, the runner cannot marshal the "
                f"broken string over gRPC, and status.result comes back empty "
                f"while the run still reports Succeeded. Use ASCII."
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


def _check_web_endpoint(persona_name, persona, web, warnings):
    """Check the web endpoint is switched on from values and nowhere else.

    Listing the skill on the persona would work, and would put a trigger in
    front of an agent without that being visible next to the other per-cluster
    decisions — the same reason `enabled` and `policyRef` are rejected in
    ensemble.yaml.
    """
    skills = persona.get("skills") or []
    for skill, tree in VALUES_ONLY_SKILLS.items():
        if skill in skills:
            raise Fail(
                f"{persona_name}: lists the {skill!r} skill. It is switched on "
                f"from {tree} in values/default.yaml.gotmpl, so that which "
                f"agents carry a testing surface is readable in one place."
            )
    params = persona.get("skillParams") or {}
    overlap = sorted(set(params) & set(VALUES_ONLY_SKILLS))
    if overlap:
        raise Fail(
            f"{persona_name}: sets skillParams for {', '.join(overlap)}, which "
            f"the templates overwrite from values at render time"
        )

    if web is None:
        return
    if not (web.get("enabled") or (web.get("personas") or {}).get(persona_name, {}).get("enabled")):
        return
    writable = sorted(
        tool
        for tool in persona.get("toolPolicy", {}).get("allow", [])
        if tool in WRITE_TOOLS
    )
    if writable:
        warnings.append(
            f"{persona_name}: has a web endpoint and holds the write tool(s) "
            f"{', '.join(writable)}, so anything that can reach the endpoint can "
            f"make it write. Turn the endpoint off outside a test."
        )


def _check_unknown_web_endpoint_personas(ensemble_name, persona_names):
    """A typo under `personas:` silently leaves that agent on the default."""
    web = _web_endpoint_config(ensemble_name)
    if not web:
        return
    unknown = sorted(set(web.get("personas") or {}) - set(persona_names))
    if unknown:
        raise Fail(
            f"sympozium_web_endpoint.ensembles.{ensemble_name}.personas names "
            f"{', '.join(unknown)}, which is not a persona in this ensemble"
        )


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
    verbosity = str(override.get("verbosity") or delivery.get("verbosity") or "normal").lower()
    notify = str(override.get("notify") or delivery.get("notify") or "always").lower()

    bound = bool(persona.get("channels"))
    prompt = (project / persona["systemPromptFile"]).read_text(encoding="utf-8")
    _check_unquoted_args(f"{project.name}/{persona['systemPromptFile']}", prompt)
    _check_fill_direction(f"{project.name}/{persona['systemPromptFile']}", prompt)

    if not bound:
        for token in PROMPT_TOKENS:
            if token in prompt:
                raise Fail(
                    f"{persona_name}: its system prompt holds {token}, but the "
                    f"persona is bound to no channel, so nothing substitutes it "
                    f"and the render fails"
                )
        if override:
            warnings.append(
                f"{persona_name}: has sympozium_delivery overrides but is bound "
                f"to no channel, so they do nothing"
            )
        return

    if not channel:
        raise Fail(
            f"{persona_name}: bound to a channel, but neither the ensemble nor "
            f"its persona override sets sympozium_delivery.channel — nothing "
            f"tells send_channel_message where to post"
        )
    if verbosity not in VERBOSITY_LEVELS:
        raise Fail(
            f"{persona_name}: verbosity {verbosity!r} is not one of "
            f"{', '.join(sorted(VERBOSITY_LEVELS))}"
        )
    if notify not in NOTIFY_LEVELS:
        raise Fail(
            f"{persona_name}: notify {notify!r} is not one of always, onChange, never"
        )
    for kind, level in (("delivery", verbosity), ("notify", notify)):
        if not (BASE / "prompts" / kind / f"{level}.md").is_file():
            raise Fail(f"{persona_name}: no prompts/{kind}/{level}.md for {level!r}")

    if "{{ DELIVERY }}" not in prompt:
        raise Fail(
            f"{persona_name}: bound to a channel and allowed to post, but its "
            f"system prompt has no {{{{ DELIVERY }}}} token, so no delivery rule "
            f"ever reaches the model and it will decide for itself"
        )
    if notify == "onchange" and "## What counts as a change" not in prompt:
        raise Fail(
            f"{persona_name}: notify is onChange, but its system prompt has no "
            f"'## What counts as a change' section for prompts/notify/onchange.md "
            f"to point at — the criteria are persona-specific and cannot live in "
            f"the shared file"
        )


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


def _check_channels(persona_name, persona, channel_secrets, warnings):
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
            f"no channel, so there is nowhere for it to post"
        )
    if channels and "send_channel_message" not in allowed:
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


def _check_persona(project, path, used, channel_secrets, delivery, web, warnings):
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

    _check_tools(name, persona, warnings)
    _check_channels(name, persona, channel_secrets, warnings)
    _check_delivery(project, name, persona, delivery, warnings)
    _check_web_endpoint(name, persona, web, warnings)
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
    web = _web_endpoint_config(name)
    names = [
        _check_persona(project, path, used, channel_secrets, delivery, web, warnings)
        for path in persona_files
    ]
    _check_unknown_delivery_personas(name, names)
    _check_unknown_web_endpoint_personas(name, names)

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

    try:
        _check_shared_prompts()
    except Fail as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    values = _values() or {}
    known = {path.name for path in projects}
    web_root = values.get("sympozium_web_endpoint") or {}
    stray = sorted(set(web_root) - {"enabled", "ensembles"})
    if stray:
        print(
            f"error: sympozium_web_endpoint has unexpected key(s) "
            f"{', '.join(stray)} at its root. Only 'enabled' (the master "
            f"switch) and 'ensembles' belong there; per-ensemble entries go "
            f"under 'ensembles:'.",
            file=sys.stderr,
        )
        return 1
    for tree, entries in (
        ("sympozium_delivery", values.get("sympozium_delivery") or {}),
        ("sympozium_web_endpoint.ensembles", web_root.get("ensembles") or {}),
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
