"""Text shaping for tool results.

Results are compact text tables rather than JSON. A 4B model reads a table and
copies rows out of it; JSON costs two to three times the tokens for the same
figures and invites the model to re-derive values from nested fields.

This module is also where **ages become facts**. Nothing in an agent run injects
a clock and no MCP server in this fleet exposes one, so the old prompts forbade
any date or duration the model had not read from a tool result — which left
"expires in 21 days" impossible to express, since the raw `notAfter` date is
uninterpretable without knowing today. The server has a clock, so it does the
subtraction and returns the *age*, which is then a tool result like any other
and needs no clock at the model's end.
"""

from __future__ import annotations

import datetime as _datetime
import logging

from .prometheus import UNAVAILABLE

logger = logging.getLogger(__name__)

# Only ASCII in rendered output. `status.result` is dropped whenever the reply
# carries invalid UTF-8: the runner ships it to the controller over gRPC,
# protobuf refuses to marshal a bad string, and the run still reports
# `Succeeded` with no `error`. The old delivery header told the model to echo a
# middot (U+00B7) verbatim and it sometimes emitted a broken byte pair, losing
# the whole report. Nothing this server emits can start that.
_ASCII_FALLBACK = {"·": "-", "—": "-", "–": "-", "→": "->", "°": ""}


def ascii_only(text: str) -> str:
    """Fold known non-ASCII to ASCII and drop the rest."""
    for source, replacement in _ASCII_FALLBACK.items():
        text = text.replace(source, replacement)
    return text.encode("ascii", errors="ignore").decode("ascii")


def number(value: float | None, digits: int = 1, suffix: str = "") -> str:
    """Format a metric, or the `unavailable` literal when there is none.

    `unavailable` means *the query answered nothing*. It is never `0`, never an
    estimate, and never a value borrowed from a different metric — relabelling
    `k8s_nodes_top` memory as disk is how a 5%-full control-plane disk was
    reported as "79% disk fill (CRITICAL)".
    """
    if value is None:
        return UNAVAILABLE
    return f"{value:.{digits}f}{suffix}"


def bytes_human(value: float | None) -> str:
    if value is None:
        return UNAVAILABLE
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(size) < 1024 or unit == "TiB":
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TiB"


def parse_timestamp(value: str | None) -> _datetime.datetime | None:
    """Parse a Kubernetes RFC3339 timestamp. Unparseable is ``None``."""
    if not value or not isinstance(value, str):
        return None
    try:
        return _datetime.datetime.fromisoformat(value)
    except ValueError:
        logger.warning("unparseable timestamp %r", value)
        return None


def age(value: str | None, *, now: _datetime.datetime | None = None) -> str:
    """Render how long ago ``value`` was, as ``3.2d ago`` / ``in 14.0d``.

    The sign is spelled out rather than left to a minus sign, because "expires
    in 14 days" and "expired 14 days ago" are opposite findings and a leading
    `-` is the easiest character in a table for a model to drop.
    """
    stamp = parse_timestamp(value)
    if stamp is None:
        return UNAVAILABLE
    reference = now or _datetime.datetime.now(_datetime.UTC)
    delta = (reference - stamp).total_seconds()
    if abs(delta) < 3600:
        return f"{abs(delta) / 60:.0f}m {'ago' if delta >= 0 else 'from now'}"
    days = abs(delta) / 86400
    if days < 1:
        return f"{abs(delta) / 3600:.1f}h {'ago' if delta >= 0 else 'from now'}"
    return f"{days:.1f}d ago" if delta >= 0 else f"in {days:.1f}d"


def days_until(value: str | None, *, now: _datetime.datetime | None = None) -> float | None:
    """Signed days until ``value``; negative is in the past. ``None`` if unparseable."""
    stamp = parse_timestamp(value)
    if stamp is None:
        return None
    reference = now or _datetime.datetime.now(_datetime.UTC)
    return (stamp - reference).total_seconds() / 86400


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Render a fixed-width table as a list of lines, header underlined.

    Returned as lines rather than a string so the byte budget can drop whole
    rows — truncating mid-line would leave a number without its label.
    """
    if not rows:
        return ["(no rows)"]
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row[: len(widths)]):
            widths[index] = max(widths[index], len(cell))
    lines = ["  ".join(header.ljust(widths[i]) for i, header in enumerate(headers)).rstrip()]
    lines.append("  ".join("-" * width for width in widths))
    for row in rows:
        padded = list(row) + [""] * (len(headers) - len(row))
        lines.append("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(padded)).rstrip())
    return lines
