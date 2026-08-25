"""Entry point for the MCP servers.

Usage:
    python -m mcp_runner --project homelab_facts [--host 0.0.0.0] [--port 8080]

Projects are discovered the same way ``dlt_runner`` discovers its pipelines: any
installed package exposing ``register(registry)`` is a valid project. A second
MCP server later is another ``projects/<name>/``.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys

from .server import Registry, build_app

logger = logging.getLogger(__name__)


def build_registry(project: str) -> Registry:
    module = importlib.import_module(project)
    registry = Registry()
    module.register(registry)
    return registry


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s|[%(levelname)s]|%(name)s|%(message)s",
    )

    parser = argparse.ArgumentParser(prog="mcp_runner")
    parser.add_argument("--project", required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="print the tool manifest and exit, without binding a port",
    )
    parsed = parser.parse_args(argv)

    try:
        registry = build_registry(parsed.project)
    except ModuleNotFoundError:
        parser.error(f"no such project: {parsed.project!r}")

    if parsed.list_tools:
        for tool in registry.describe():
            print(f"{tool['name']}\n    {tool['description'].splitlines()[0]}")
        return

    logger.info(
        "serving project=%s tools=%d on %s:%d",
        parsed.project,
        len(registry.tools),
        parsed.host,
        parsed.port,
    )

    import uvicorn

    uvicorn.run(
        build_app(registry),
        host=parsed.host,
        port=parsed.port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
