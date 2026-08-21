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

SCHEDULE_TYPES = {"heartbeat", "scheduled", "sweep"}
FIRST_TICKS = {"immediate", "afterInterval"}

# Keys the Helm templates stamp onto a persona from the project's `defaults:`
# block when the persona does not set them itself.
DEFAULTABLE = ("provider", "model", "runTimeout")

# Keys that belong to the cluster, not the agent, and are merged in from
# release values at render time.
VALUES_ONLY_KEYS = ("enabled", "baseURL", "policyRef")

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
    if first_tick is not None and first_tick not in FIRST_TICKS:
        raise Fail(
            f"{persona_name}: schedule.firstTick {first_tick!r} is not one of "
            f"{', '.join(sorted(FIRST_TICKS))}"
        )


def _check_persona(project, path, used, warnings):
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
    names = [_check_persona(project, path, used, warnings) for path in persona_files]

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
