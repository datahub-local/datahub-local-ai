"""Entry point for the dlt ingest/export pipelines.

Usage:
    python -m dlt_runner --pipeline <pipeline> --project <project> --target <homelab|local>

Projects and pipelines are discovered dynamically: any installed package with a module
that exposes a ``run(target)`` function is a valid project/pipeline combination.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys

SEP = "#" * 60

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s|[%(levelname)s]|%(name)s|%(message)s",
    )

    parser = argparse.ArgumentParser(prog="dlt_runner")
    parser.add_argument("--pipeline", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--target", default="homelab", choices=["homelab", "local"])
    parsed = parser.parse_args(argv)

    try:
        module = importlib.import_module(f"{parsed.project}.{parsed.pipeline}")
    except ModuleNotFoundError:
        parser.error(
            f"project '{parsed.project}' does not support pipeline '{parsed.pipeline}'"
        )

    logger.info("Starting pipeline=%s project=%s target=%s", parsed.pipeline, parsed.project, parsed.target)
    try:
        module.run(parsed.target)
    except Exception:
        logger.exception(
            "Pipeline failed: pipeline=%s project=%s target=%s", parsed.pipeline, parsed.project, parsed.target
        )
        raise
    logger.info("Pipeline succeeded: pipeline=%s project=%s target=%s", parsed.pipeline, parsed.project, parsed.target)


if __name__ == "__main__":
    main(sys.argv[1:])
