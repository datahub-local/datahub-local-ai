"""Previous-snapshot persistence, so a trend is measured rather than asserted.

"New vs still-firing vs resolved" used to depend on a 4B model reading its own
memory seeds and diffing them against a fresh alert list. It did not do that
reliably, and the seeds had grown to contain corrections of the agents' own
wrong history. Here the diff is computed against a stored snapshot, so the
model is handed the answer instead of the inputs.

A lost snapshot degrades a diff to "first observation", which every tool states
explicitly. It never produces a wrong diff — an empty store cannot look like
"nothing changed".
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from . import config

logger = logging.getLogger(__name__)


class Snapshots:
    def __init__(self, directory: str | None = None) -> None:
        self.directory = Path(directory or config.state_dir())

    def _path(self, key: str) -> Path:
        safe = "".join(char for char in key if char.isalnum() or char in "-_")
        return self.directory / f"{safe}.json"

    def load(self, key: str) -> dict[str, Any] | None:
        """Return the stored snapshot, or ``None`` if there is not a usable one.

        Any failure to read or parse is `None`, deliberately: a corrupt snapshot
        must degrade to "first observation" rather than raise, because the tool's
        primary reading is still perfectly good and losing it to a cache problem
        would be the worse outcome.
        """
        path = self._path(key)
        try:
            return json.loads(path.read_text())
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            logger.warning("discarding unreadable snapshot %s: %s", path, exc)
            return None

    def save(self, key: str, payload: dict[str, Any]) -> None:
        """Write ``payload`` atomically. A failure is logged, never raised."""
        path = self._path(key)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", dir=self.directory, delete=False, encoding="utf-8"
            ) as handle:
                json.dump(payload, handle)
                temporary = handle.name
            os.replace(temporary, path)
        except OSError as exc:
            logger.warning("could not persist snapshot %s: %s", path, exc)


def diff_keys(
    current: set[str], previous: set[str] | None
) -> tuple[list[str], list[str], list[str]]:
    """Return ``(new, continuing, resolved)`` sorted, or all-new on a first run.

    ``previous is None`` means there is no prior observation. Everything is then
    reported as newly *seen*, and the caller says so — calling it all "new" with
    no qualifier would read as a fleet-wide incident on the first run after a
    restart.
    """
    if previous is None:
        return sorted(current), [], []
    return (
        sorted(current - previous),
        sorted(current & previous),
        sorted(previous - current),
    )
