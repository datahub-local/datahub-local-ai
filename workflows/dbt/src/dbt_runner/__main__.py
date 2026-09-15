"""Entry point that runs ``dbt build`` for a pipeline against a target.

Usage:
    python -m dbt_runner --project <example_db|pi> --target <homelab|local>
                         [--select ...] [--full-refresh]

dbt runs directly on Trino (``homelab``) or DuckDB (``local``) via its adapter. CSV ingest
and the reverse-ETL export are handled by the separate ``workflows/dlt`` pipelines, not by
this runner.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# dbt project dirs live under projects/ at the project root.
# Docker sets DBT_PROJECTS_DIR=/app/projects; editable installs resolve via __file__.
PROJECTS_DIR = os.environ.get(
    "DBT_PROJECTS_DIR",
    str(Path(__file__).resolve().parent.parent.parent / "projects"),  # src/dbt_runner -> src -> root -> projects/
)


def _run_dbt(project: str, target: str, select: str | None, full_refresh: bool) -> None:
    from dbt.cli.main import dbtRunner

    project_dir = os.path.join(PROJECTS_DIR, project)
    args = [
        "build",
        "--project-dir", project_dir,
        "--profiles-dir", project_dir,
        "--target", target,
    ]
    if select:
        args += ["--select", select]
    if full_refresh:
        args.append("--full-refresh")

    result = dbtRunner().invoke(args)
    if not result.success:
        if result.exception:
            raise result.exception
        raise SystemExit(f"dbt build failed for project {project!r}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dbt_runner")
    parser.add_argument("--project", required=True, choices=["example_db", "pi", "bodega", "finance"])
    parser.add_argument("--target", default="homelab", choices=["homelab", "local"])
    parser.add_argument("--select", default="")
    parser.add_argument("--full-refresh", action="store_true")
    parsed = parser.parse_args(argv)

    if parsed.select:
        print(f"  select={parsed.select}", end="")
    if parsed.full_refresh:
        print("  --full-refresh", end="")

    _run_dbt(parsed.project, parsed.target, parsed.select or None, parsed.full_refresh)


if __name__ == "__main__":
    main(sys.argv[1:])
