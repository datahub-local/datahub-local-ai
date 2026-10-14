"""Enrich step: LLM-categorise distinct product descriptions into silver.bodega.products.

Reads ``silver.bodega.invoice_items`` for unseen (description_clean, supermarket) pairs,
calls OpenRouter in batches of 30, and writes the results as ``silver.bodega.products``.
Already-categorised products are never re-queried.

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

PIPELINE_NAME = "bodega_enrich"
DATASET_NAME = "bodega"
TABLE_NAME = "products"

CATEGORIES_FILE = Path(__file__).parent / "categories.csv"

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


SYSTEM_PROMPT_TEMPLATE = Template("""You are an expert at categorising $language supermarket products.
You will be given a list of raw product descriptions written in $language (abbreviated text);
classify each one using the categories below (category names, descriptions and examples are in English).

Allowed categories:
$categories

Return ONLY a JSON object of the form {"items": [...]}, where "items" is an array
with one object per description, in the same order, with fields:
  category (one of the allowed values), subcategory (specific label IN ENGLISH, max 30 chars),
  is_weighted (true if typically sold by kg/weight, else false).
No explanation, no markdown, just the JSON object.""")


def _build_system_prompt() -> str:
    return SYSTEM_PROMPT_TEMPLATE.substitute(
        language=config.product_language(),
        categories=_format_categories(_load_categories()),
    )


def _categorize_batch(descriptions: list[str], base_url: str, api_key: str, model_id: str) -> list[dict]:
    try:
        content = call_llm(
            json.dumps(descriptions),
            base_url=base_url,
            api_key=api_key,
            model_id=model_id,
            system_prompt=_build_system_prompt(),
            timeout=config.llm_timeout(),
            response_format={"type": "json_object"},
        )
        parsed = json.loads(content)
        items = parsed if isinstance(parsed, list) else parsed.get("items", parsed.get("results", []))
        if len(items) == len(descriptions):
            return items
        logger.warning(
            "LLM returned %d categorized items for a batch of %d descriptions; marking batch as PARSE_ERROR",
            len(items), len(descriptions),
        )
    except Exception:
        logger.warning("Failed to categorize batch of %d descriptions", len(descriptions), exc_info=True)
    return [{"category": "OTHER", "subcategory": "PARSE_ERROR", "is_weighted": False}] * len(descriptions)


@dlt.resource(
    name=TABLE_NAME,
    write_disposition="merge",
    primary_key=["description_clean", "supermarket"],
)
def products(new_descriptions: list[dict], base_url: str, api_key: str, model_id: str):
    """Yield categorised product rows for the given unseen descriptions."""
    batch_size = 30
    for i in range(0, len(new_descriptions), batch_size):
        batch = new_descriptions[i : i + batch_size]
        descs = [r["description_clean"] for r in batch]
        categorized = _categorize_batch(descs, base_url, api_key, model_id)
        for row, cat in zip(batch, categorized):
            yield {
                "description_clean": row["description_clean"],
                "supermarket":       row["supermarket"],
                "category":          cat.get("category", "OTHER"),
                "subcategory":       cat.get("subcategory", "")[:30],
                "is_weighted":       cat.get("is_weighted", False),
                "categorized_at":    datetime.now(UTC).isoformat(),
                "llm_model":         model_id,
            }


def _find_new_descriptions_local(silver_duckdb_path: str) -> list[dict]:
    """Return (description_clean, supermarket) pairs not yet in products (DuckDB)."""
    import duckdb

    con = duckdb.connect(silver_duckdb_path, read_only=True)
    try:
        schema_exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='bodega'"
        ).fetchone()[0]
        if not schema_exists:
            return []

        products_exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='bodega' AND table_name='products'"
        ).fetchone()[0]
        existing: set[tuple[str, str]] = set()
        if products_exists:
            existing = {
                (r[0], r[1])
                for r in con.execute(
                    "SELECT description_clean, supermarket FROM bodega.products "
                    "WHERE subcategory != 'PARSE_ERROR'"
                ).fetchall()
            }

        items_exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='bodega' AND table_name='invoice_items'"
        ).fetchone()[0]
        if not items_exists:
            return []

        all_items = [
            {"description_clean": r[0], "supermarket": r[1]}
            for r in con.execute(
                "SELECT DISTINCT description_clean, supermarket FROM bodega.invoice_items"
            ).fetchall()
        ]
    finally:
        con.close()

    return [item for item in all_items if (item["description_clean"], item["supermarket"]) not in existing]


def _find_new_descriptions_homelab(trino_url: str) -> list[dict]:
    """Return (description_clean, supermarket) pairs not yet in products (Trino)."""
    from sqlalchemy import create_engine, text

    engine = create_engine(trino_url)
    with engine.connect() as conn:
        try:
            existing = {
                (r.description_clean, r.supermarket)
                for r in conn.execute(
                    text(
                        "SELECT description_clean, supermarket FROM silver.bodega.products "
                        "WHERE subcategory != 'PARSE_ERROR'"
                    )
                )
            }
        except Exception:
            logger.debug("silver.bodega.products not found; assuming no existing products (first run?)", exc_info=True)
            existing = set()

        all_items = [
            {"description_clean": r.description_clean, "supermarket": r.supermarket}
            for r in conn.execute(
                text("SELECT DISTINCT description_clean, supermarket FROM silver.bodega.invoice_items")
            )
        ]

    return [item for item in all_items if (item["description_clean"], item["supermarket"]) not in existing]


def run(target: str):
    config.validate_target(target)

    base_url, api_key, model_id = config.llm_settings()

    if target == "local":
        new_descs = _find_new_descriptions_local(config.duckdb_path("silver"))
        destination = dlt.destinations.duckdb(config.duckdb_path("silver"))
    else:
        new_descs = _find_new_descriptions_homelab(config.trino_url())
        config.configure_iceberg_env("silver")
        destination = dlt.destinations.filesystem(
            bucket_url=f"s3://{config.silver_bucket()}",
            credentials=config.s3_credentials(),
        )

    logger.info("bodega_enrich: found %d new product descriptions to categorize", len(new_descs))
    if not new_descs:
        return "No new product descriptions to categorise."

    resource = products(new_descs, base_url=base_url, api_key=api_key, model_id=model_id)
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
