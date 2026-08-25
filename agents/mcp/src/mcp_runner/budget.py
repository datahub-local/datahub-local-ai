"""Byte budgets for tool results.

A "fat tool" means *few calls*, never *big answers*. On 2026-08-24 a single
~16 KB tool result ended a run with no report at all: `gitops-auditor` made four
calls for 24,126 result bytes and produced `terminal turn had empty text`, where
its run four hours earlier made five calls for 8,483 bytes and wrote a normal
report. The difference was one tool returning ~16 KB by itself. That was **not**
a context overflow — cumulative input was 25,423 tokens against a 65,536 window.
A 4B model simply stops producing a final turn when one answer is that large.

So every tool declares a budget and truncates to it *in code*, and the
truncation is announced in the result rather than being silent: a report built
on a quietly-cut answer is the invented-number failure in a new place.
"""

from __future__ import annotations

# Well under the ~16 KB that reproducibly kills a final turn, and above the
# 8,483-byte run that worked. Per tool, not per run.
DEFAULT_BUDGET_BYTES = 4096

# What a truncation notice costs, so the notice itself can never push a result
# back over its budget.
_NOTICE_RESERVE = 160


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def truncate_lines(
    lines: list[str],
    budget: int = DEFAULT_BUDGET_BYTES,
    *,
    unit: str = "rows",
) -> str:
    """Join ``lines`` newline-separated, dropping whole lines to fit ``budget``.

    Truncation is by line, never mid-line: half a row of a table is a number
    without its label, which is exactly the shape a model misreads. When lines
    are dropped the result ends with a count of what was left out, so the model
    can say the answer was partial instead of presenting it as complete.
    """
    kept: list[str] = []
    used = 0
    limit = budget - _NOTICE_RESERVE

    for index, line in enumerate(lines):
        cost = _byte_len(line) + 1
        if used + cost > limit and index < len(lines):
            dropped = len(lines) - len(kept)
            kept.append(f"... TRUNCATED: {dropped} more {unit} not shown (byte budget {budget}).")
            return "\n".join(kept)
        kept.append(line)
        used += cost

    return "\n".join(kept)


def clamp(text: str, budget: int = DEFAULT_BUDGET_BYTES) -> str:
    """Last-resort guard for text that is not line-structured.

    Cuts on a UTF-8 character boundary. `status.result` is dropped outright
    whenever the reply carries invalid UTF-8 — the runner ships it to the
    controller over gRPC and protobuf refuses to marshal a bad string, while the
    run still reports `Succeeded` with no `error` — so a truncation that splits a
    multi-byte character would turn a large answer into a silently missing one.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= budget:
        return text
    head = encoded[: budget - _NOTICE_RESERVE].decode("utf-8", errors="ignore")
    return f"{head}\n... TRUNCATED at {budget} bytes."
