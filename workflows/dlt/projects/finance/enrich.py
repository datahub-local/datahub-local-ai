"""Enrich step: LLM-categorise distinct payees into silver.finance.merchant_categories.

Reads ``silver.finance.transactions`` for unseen ``payee_clean`` values, calls the
LLM in batches of 30, and writes the results as ``silver.finance.merchant_categories``
(spec 005 §4.5). Already-categorised payees are never re-queried; a failed batch lands
as ``subcategory = PARSE_ERROR`` and is retried on the next run — never dropped.

Keyed on ``payee_clean`` alone, **not** ``(payee_clean, institution)``: the same merchant
spelled differently by two banks normalises to one key, so it is categorised once. The
institution is kept only as ``first_seen_institution`` for debugging.

- ``local``   → reads DuckDB silver.duckdb, writes back to DuckDB silver.duckdb.
- ``homelab`` → reads Trino (Iceberg), writes to Iceberg via Apache Polaris REST + S3.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from string import Template

import dlt

from dlt_runner.llm import call_llm

from . import config

PIPELINE_NAME = "finance_enrich"
DATASET_NAME = "finance"
TABLE_NAME = "merchant_categories"

CATEGORIES_FILE = Path(__file__).parent / "categories.csv"
BATCH_SIZE = 30

logger = logging.getLogger(__name__)


def _load_categories() -> list[dict]:
    with CATEGORIES_FILE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _format_categories(categories: list[dict]) -> str:
    lines = []
    for c in categories:
        line = f"- {c['category']}: {c['description']}"
        if c.get("examples"):
            line += f" (e.g. {c['examples']})"
        lines.append(line)
    return "\n".join(lines)


SYSTEM_PROMPT_TEMPLATE = Template("""You are an expert at categorising $language bank transactions.
You will be given a list of payment descriptions (payee text) written in $language;
classify each one using the categories below (category names, descriptions and examples are in English).

Allowed categories:
$categories

Return ONLY a JSON object of the form {"items": [...]}, where "items" is an array
with one object per payee, in the same order, with fields:
  category (one of the allowed values), subcategory (specific label IN ENGLISH, max 30 chars).
No explanation, no markdown, just the JSON object.""")


def _build_system_prompt() -> str:
    return SYSTEM_PROMPT_TEMPLATE.substitute(
        language=config.payee_language(),
        categories=_format_categories(_load_categories()),
    )


def _categorize_batch(payees: list[str], base_url: str, api_key: str, model_id: str) -> list[dict]:
    try:
        content = call_llm(
            json.dumps(payees),
            base_url=base_url,
            api_key=api_key,
            model_id=model_id,
            system_prompt=_build_system_prompt(),
            timeout=config.llm_timeout(),
            response_format={"type": "json_object"},
        )
        parsed = json.loads(content)
        items = parsed if isinstance(parsed, list) else parsed.get("items", parsed.get("results", []))
        if len(items) == len(payees):
            return items
        logger.warning(
            "LLM returned %d categorised items for a batch of %d payees; marking batch as PARSE_ERROR",
            len(items), len(payees),
        )
    except Exception:
        logger.warning("Failed to categorise batch of %d payees", len(payees), exc_info=True)
    return [{"category": "OTHER", "subcategory": "PARSE_ERROR"}] * len(payees)


@dlt.resource(
    name=TABLE_NAME,
    write_disposition="merge",
    primary_key=["payee_clean"],
)
def merchant_categories(new_payees: list[dict], base_url: str, api_key: str, model_id: str):
    """Yield categorised payee rows for the given unseen payees."""
    for i in range(0, len(new_payees), BATCH_SIZE):
        batch = new_payees[i : i + BATCH_SIZE]
        payees = [r["payee_clean"] for r in batch]
        categorized = _categorize_batch(payees, base_url, api_key, model_id)
        for row, cat in zip(batch, categorized):
            yield {
                "payee_clean":            row["payee_clean"],
                "category":               cat.get("category", "OTHER"),
                "subcategory":            cat.get("subcategory", "")[:30],
                "first_seen_institution": row.get("institution_id"),
                "categorized_at":         datetime.now(UTC).isoformat(),
                "llm_model":              model_id,
            }


def _find_new_payees_local(silver_duckdb_path: str) -> list[dict]:
    """Return unseen (payee_clean, institution_id) pairs (DuckDB)."""
    import duckdb

    con = duckdb.connect(silver_duckdb_path, read_only=True)
    try:
        schema_exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='finance'"
        ).fetchone()[0]
        if not schema_exists:
            return []

        categories_exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='finance' AND table_name='merchant_categories'"
        ).fetchone()[0]
        existing: set[str] = set()
        if categories_exists:
            existing = {
                r[0]
                for r in con.execute(
                    "SELECT payee_clean FROM finance.merchant_categories "
                    "WHERE subcategory != 'PARSE_ERROR'"
                ).fetchall()
            }

        transactions_exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='finance' AND table_name='transactions'"
        ).fetchone()[0]
        if not transactions_exists:
            return []

        all_payees = [
            {"payee_clean": r[0], "institution_id": r[1]}
            for r in con.execute(
                "SELECT payee_clean, min(institution_id) FROM finance.transactions "
                "WHERE payee_clean IS NOT NULL AND payee_clean != '' "
                "GROUP BY payee_clean"
            ).fetchall()
        ]
    finally:
        con.close()

    return [p for p in all_payees if p["payee_clean"] not in existing]


def _find_new_payees_homelab(trino_url: str) -> list[dict]:
    """Return unseen (payee_clean, institution_id) pairs (Trino)."""
    from sqlalchemy import create_engine, text

    engine = create_engine(trino_url)
    with engine.connect() as conn:
        try:
            existing = {
                r.payee_clean
                for r in conn.execute(
                    text(
                        "SELECT payee_clean FROM silver.finance.merchant_categories "
                        "WHERE subcategory != 'PARSE_ERROR'"
                    )
                )
            }
        except Exception:
            logger.debug(
                "silver.finance.merchant_categories not found; assuming none (first run?)",
                exc_info=True,
            )
            existing = set()

        all_payees = [
            {"payee_clean": r.payee_clean, "institution_id": r.institution_id}
            for r in conn.execute(
                text(
                    "SELECT payee_clean, min(institution_id) AS institution_id "
                    "FROM silver.finance.transactions "
                    "WHERE payee_clean IS NOT NULL AND payee_clean != '' "
                    "GROUP BY payee_clean"
                )
            )
        ]

    return [p for p in all_payees if p["payee_clean"] not in existing]


def run(target: str):
    config.validate_target(target)

    base_url, api_key, model_id = config.llm_settings()

    if target == "local":
        new_payees = _find_new_payees_local(config.duckdb_path("silver"))
        destination = dlt.destinations.duckdb(config.duckdb_path("silver"))
    else:
        new_payees = _find_new_payees_homelab(config.trino_url())
        config.configure_iceberg_env("silver")
        destination = dlt.destinations.filesystem(
            bucket_url=f"s3://{config.silver_bucket()}",
            credentials=config.s3_credentials(),
        )

    logger.info("finance_enrich: found %d new payees to categorise", len(new_payees))
    if not new_payees:
        return "No new payees to categorise."

    resource = merchant_categories(new_payees, base_url=base_url, api_key=api_key, model_id=model_id)
    if target != "local":
        resource.apply_hints(table_format="iceberg")

    pipeline = dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination=destination,
        dataset_name=DATASET_NAME,
    )
    load_info = pipeline.run(resource)
    logger.info("%s: row counts %s", PIPELINE_NAME, pipeline.last_trace.last_normalize_info.row_counts)
    return load_info
