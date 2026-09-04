"""`semantic-compile` - the CI gate on the semantic registry.

Offline by design: it runs `dbt parse` (no warehouse, no credentials, exactly as
workflows/dbt/tests/ already does) and validates the registry against the
resulting manifest. The temptation to reach for a live DESCRIBE "because it is
more real" is the failure mode to resist - a Trino permission change here is a
coordinator restart, so a red build would routinely mean "someone rolled the
coordinator" rather than "a column moved".

What it gates:

  1. schema and structure of the registry YAML
  2. every ref() resolves to a dbt model
  3. every expr resolves to a *documented* column of that model, with a bare
     column reference required so no SQL fragment can hide in the registry
  4. mandatory excludes/description/owner, unique metric names, grain floors,
     no avg over a pre-aggregated total, no undeclared cross-model metric
  5. stamps registry_version = git sha

Usage:
    uv run python semantic/compile.py [--project bodega] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
DBT_ROOT = HERE.parent
REPO_ROOT = DBT_ROOT.parent.parent

# Shared with the MCP server so the gate and the server apply identical rules.
# Expects that repo beside this one; MCP_REPO overrides.
MCP_REPO = Path(os.environ.get("MCP_REPO", REPO_ROOT.parent / "datahub-local-ai-mcp"))
REGISTRY_MODULE = MCP_REPO / "servers" / "semantic" / "registry.py"


def _load_registry_module():
    """Import `registry.py` by path, not as part of the `semantic` package.

    The gate and the MCP server must apply byte-identical rules, so the module
    is shared rather than copied. Importing it as `semantic.registry` would run
    the package `__init__`, which imports `mcp_runner` - a dependency of the mcp
    repository that this dbt environment does not have and does not need.
    """
    import importlib.util

    if not REGISTRY_MODULE.is_file():
        raise SystemExit(
            f"no registry module at {REGISTRY_MODULE}.\n"
            f"The validation rules are shared with the MCP server rather than copied, so this "
            f"gate needs the datahub-local-ai-mcp repository checked out beside this one, or "
            f"MCP_REPO pointing at it."
        )

    spec = importlib.util.spec_from_file_location("_semantic_registry", REGISTRY_MODULE)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: @dataclass resolves annotations through
    # sys.modules[cls.__module__], which is None for a module loaded by path.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_registry_module = _load_registry_module()
Registry = _registry_module.Registry
RegistryError = _registry_module.RegistryError
bind_tables = _registry_module.bind_tables
load_registry = _registry_module.load
validate_registry = _registry_module.validate_registry


def dbt_manifest(project: str) -> dict:
    """Parse the dbt project offline and return its manifest."""
    from dbt.cli.main import dbtRunner

    project_dir = DBT_ROOT / "projects" / project
    result = dbtRunner().invoke(
        [
            "parse",
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(project_dir),
            "--target",
            "local",
        ]
    )
    if not result.success:
        raise SystemExit(f"dbt parse failed for {project}: {getattr(result, 'exception', '')}")
    return json.loads((project_dir / "target" / "manifest.json").read_text())


def git_sha() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=DBT_ROOT,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", str(HERE)],
        capture_output=True,
        text=True,
        check=False,
        cwd=DBT_ROOT,
    ).stdout.strip()
    return f"{sha}-dirty" if dirty else sha


def compile_registry(path: Path, manifest: dict, version: str) -> tuple[Registry, list[str]]:
    """Load and fully validate one registry file. Never raises for a content error."""
    try:
        registry = load_registry(path, version=version, manifest=manifest)
    except RegistryError as exc:
        raw = yaml.safe_load(path.read_text()) or {}
        return Registry(version=version), str(exc).splitlines() or validate_registry(
            Registry(), raw, manifest
        )
    bind_tables(registry, manifest)
    unbound = [model.name for model in registry.models.values() if not model.table]
    return registry, [f"semantic_model {name!r}: no table resolved from the manifest" for name in unbound]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="semantic-compile")
    parser.add_argument("--project", default="bodega", help="dbt project the registry references")
    parser.add_argument("--registry", default=None, help="registry YAML (default: <project>.yaml)")
    parser.add_argument("--json", dest="json_out", default=None, help="write the compiled artifact")
    args = parser.parse_args(argv)

    path = Path(args.registry) if args.registry else HERE / f"{args.project}.yaml"
    if not path.exists():
        print(f"semantic-compile: no registry at {path}", file=sys.stderr)
        return 2

    version = git_sha()
    manifest = dbt_manifest(args.project)
    registry, problems = compile_registry(path, manifest, version)

    if problems:
        print(f"semantic-compile: FAILED with {len(problems)} problem(s) in {path.name}\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"semantic-compile: OK  {path.name}  registry_version={version}")
    print(f"  {len(registry.models)} semantic model(s), {len(registry.metrics)} metric(s)")
    for metric in sorted(registry.metrics.values(), key=lambda m: m.name):
        model = registry.model_for(metric)
        print(f"    {metric.name:<24} {metric.type:<6} -> {model.table}")

    if args.json_out:
        artifact = {
            "registry_version": version,
            "source": path.name,
            "metrics": {
                name: {
                    "label": metric.label,
                    "type": metric.type,
                    "grain_min": metric.grain_min,
                    "table": registry.model_for(metric).table,
                    "excludes": metric.excludes,
                }
                for name, metric in registry.metrics.items()
            },
        }
        Path(args.json_out).write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
        print(f"  wrote {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
