"""The only module that knows how to talk to Prometheus.

Everything the old prompts had to teach a 4B model lives here as code:

- **No datasource uid.** We query Prometheus directly, so there is no uid to
  resolve and no Loki to mistake for it.
- **No `endTime`.** An instant query with no `time` parameter is evaluated at
  server-now. The prompts spent 2.3 KB explaining that `endTime` is the literal
  word `now`, three characters, after a run sent `endTime 1725489600` —
  September 2024 — and read six empty results as a dead fleet.
- **No `queryType`.** `instant()` and `range_()` are separate functions, so the
  choice is made by the caller's intent rather than by a string argument that
  defaults to `range` and then fails on a missing `stepSeconds`.
- **A counter is never returned raw.** `increase_()` wraps the expression, so a
  caller cannot drop the wrapper the way a run did on 2026-08-24, sending
  `m[1h]` and labelling the bare counter as the increase.

`UNAVAILABLE` is the other half of the contract. A query that errors or returns
no series yields the sentinel, never `0` and never an estimate: an error is not
a healthy reading, and a mandatory report format that cannot express absence
gets filled with invented numbers instead.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from . import config

logger = logging.getLogger(__name__)

# The literal a report prints when a metric answered nothing. It is a value, not
# an error: `unavailable` in a column is a legitimate reading, honestly reported.
UNAVAILABLE = "unavailable"


class PrometheusError(RuntimeError):
    """A query failed. Distinct from an empty result, which is a real answer."""


@dataclass(frozen=True)
class Reading:
    """Samples keyed by a label, plus whether the query succeeded at all.

    ``ok=False`` with an empty ``values`` is "unknown"; ``ok=True`` with an empty
    ``values`` is "nothing matched", which is a real answer.
    """

    values: dict[str, float]
    ok: bool

    def covered(self) -> set[str]:
        return set(self.values)


class Prometheus:
    def __init__(self, url: str | None = None, timeout: float | None = None) -> None:
        self.url = (url or config.prometheus_url()).rstrip("/")
        self.timeout = timeout if timeout is not None else config.prometheus_timeout()

    # -- transport -----------------------------------------------------------

    def _get(self, path: str, params: dict[str, str]) -> dict:
        try:
            response = httpx.get(f"{self.url}{path}", params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PrometheusError(f"{path} failed: {exc}") from exc
        if payload.get("status") != "success":
            raise PrometheusError(f"{path} returned status={payload.get('status')!r}")
        return payload.get("data") or {}

    # -- queries -------------------------------------------------------------

    def instant(self, expr: str) -> list[dict]:
        """Evaluate ``expr`` at server-now, returning the raw sample list.

        No `time` parameter is sent. Prometheus then evaluates at its own clock,
        which is the only clock in this system that is known to be right —
        nothing in an agent run injects one.
        """
        data = self._get("/api/v1/query", {"query": expr})
        return data.get("result") or []

    def range_(self, expr: str, *, since_seconds: int = 21600, step_seconds: int = 300) -> list[dict]:
        """Evaluate ``expr`` over the last ``since_seconds``, ending now.

        Prometheus rejects relative times outright — `start=now-1h` answers
        `cannot parse "now-1h" to a valid timestamp`. Relative times are a
        Grafana convenience, and this is the direct API, so the window is
        resolved to unix timestamps here. This is the one place in the server
        that reads a clock, and it reads the local one only to bound a window;
        every timestamp a report prints comes from a tool result.
        """
        end = time.time()
        data = self._get(
            "/api/v1/query_range",
            {
                "query": expr,
                "start": f"{end - since_seconds:.3f}",
                "end": f"{end:.3f}",
                "step": str(step_seconds),
            },
        )
        return data.get("result") or []

    def metric_type(self, metric: str) -> str | None:
        """Metric type from Prometheus's metadata API — never from the suffix.

        A suffix rule gets this cluster wrong in both directions:
        `cnpg_backends_total` and `cnpg_backends_waiting_total` are **gauges**
        despite `_total`, while `cnpg_pg_stat_archiver_failed_count` is a
        **counter** despite `_count`. Reading the counter as a state paged a
        CRITICAL "recovery is silently broken" off a lifetime total of 2 whose
        last failure was 5.4 days old.
        """
        data = self._get("/api/v1/metadata", {"metric": metric})
        entries = data.get(metric) if isinstance(data, dict) else None
        if not entries:
            return None
        return entries[0].get("type")

    # -- shaping -------------------------------------------------------------

    def scalar_by(self, expr: str, label: str) -> dict[str, float]:
        """Return ``{label_value: sample}`` for a query expected to be keyed by ``label``.

        A series missing the label is dropped rather than given a made-up key.
        Callers compare the returned keys against the set they expected and emit
        `UNAVAILABLE` for the difference, which is how a broken join shows up as
        scattered absences instead of as a plausible wrong row.
        """
        out: dict[str, float] = {}
        for series in self.instant(expr):
            key = (series.get("metric") or {}).get(label)
            if not key:
                continue
            try:
                out[key] = float(series["value"][1])
            except (KeyError, IndexError, TypeError, ValueError):
                continue
        return out

    def try_scalar_by(self, expr: str, label: str) -> dict[str, float]:
        """``scalar_by`` that turns a query failure into an empty answer.

        Used where one unavailable metric must not cost the whole report. The
        caller renders `UNAVAILABLE` for the missing keys, so the absence is
        stated rather than hidden — and logged here so it is diagnosable.
        """
        return self.reading(expr, label).values

    def reading(self, expr: str, label: str) -> Reading:
        """``scalar_by`` plus whether the query itself succeeded.

        The two are different facts and get different words in a report. A query
        that *answered nothing for one node* means that node has no such sensor,
        which is the hardware and not a fault. A query that *failed* means the
        value is unknown for every node. Collapsing them is how `unavailable`
        came to absorb a broken join and hide it: absence needs a definition, or
        it swallows every bug.
        """
        try:
            return Reading(values=self.scalar_by(expr, label), ok=True)
        except PrometheusError as exc:
            logger.warning("query failed, reporting unavailable: %s (%s)", expr, exc)
            return Reading(values={}, ok=False)


# -- expression helpers ------------------------------------------------------
#
# These build the expressions that the old prompts asked the model to assemble.
# Each one encodes a mistake that reached Slack.


def used_percent(available: str, capacity: str, selector: str = "") -> str:
    """Percent **used** — `100 * (1 - available/capacity)`, never the bare ratio.

    `available / capacity` is the fraction *free*. Reporting it as fill inverts
    every finding: it flags the emptiest volumes and can never flag a full one,
    which is how a 2%-used volume was called "97.9% full, write operations
    failing" on every run for days.
    """
    return f"100 * (1 - {available}{selector} / {capacity}{selector})"


def increase_(metric: str, window: str = "1h") -> str:
    """`increase(metric[window])` — the whole call, wrapper included.

    A caller cannot pass the inner range selector by accident, which is what a
    run did on 2026-08-24: it sent `m[1h]` and labelled the raw counter it got
    back as the increase.
    """
    return f"increase({metric}[{window}])"


def rate_percent(metric: str, window: str = "5m") -> str:
    """Percentage of ``window`` spent in the state ``metric`` accumulates."""
    return f"100 * rate({metric}[{window}])"


def by_nodename(inner: str, aggregator: str = "max") -> str:
    """Attach machine identity to a `node_*` expression.

    **No `node_*` series in this Prometheus carries a machine name.** They are
    keyed by `instance` — an IP and port — and the only hostname anywhere is the
    `nodename` label on `node_uname_info`. Asked for a per-node table without
    being told how to bridge that, a model improvised: it wrote
    `node_apt_security_upgrades_pending by (node)` — not valid PromQL and a label
    that does not exist — on four different metrics, and elsewhere queried the
    bare metric and guessed the IP mapping. The 2026-08-24 13:25 table was wrong
    in five ways at once: four rows said `unavailable` when every figure was
    available, the NAS was given amd-1's disk percentage, and every uptime was
    wrong by two orders of magnitude.

    The join is now the only way to ask, so it cannot be dropped.
    """
    return f"{aggregator} by (nodename) ({inner} * on(instance) group_left(nodename) node_uname_info)"
