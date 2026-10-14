"""Ingest step: drain the bodega_invoices Kafka topic into the bronze medallion layer.

dlt streams parsed invoice JSON from Kafka into ``bronze.bodega.raw_invoices``, which the
dbt bodega project then reads as a source. Raw JSON arrays (items, taxes) are kept as
strings in Bronze; explosion into rows happens in Silver.

- ``local``   → DuckDB file (the same ``bronze.duckdb`` the dbt local target reads).
- ``homelab`` → Iceberg table via Apache Polaris REST + S3, staged in the temp bucket.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta

import dlt
from confluent_kafka import Consumer, KafkaError

from . import config

PIPELINE_NAME = "bodega_ingest"
DATASET_NAME = "bodega"
TABLE_NAME = "raw_invoices"

logger = logging.getLogger(__name__)


@dlt.resource(
    name=TABLE_NAME,
    write_disposition="merge",
    primary_key=["invoice_number"],
    columns={"invoice_date": {"data_type": "text"}, "_batch_timestamp": {"data_type": "text"}},
)
def raw_invoices(bootstrap_servers: str, topic: str, group_id: str = "bodega-dlt-bronze"):
    """Micro-batch Kafka consumer: drain until 3 consecutive empty polls, then return."""
    kafka_config = {
        "bootstrap.servers": bootstrap_servers,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "session.timeout.ms": 30000,
    }
    consumer = Consumer(kafka_config)
    consumer.subscribe([topic])

    ingested_at = datetime.now(UTC).isoformat()
    idle_rounds, max_idle, poll_timeout = 0, 3, 10.0
    try:
        while idle_rounds < max_idle:
            msg = consumer.poll(timeout=poll_timeout)
            if msg is None:
                idle_rounds += 1
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    idle_rounds = max_idle
                else:
                    raise RuntimeError(f"Kafka error: {msg.error()}")
                continue
            idle_rounds = 0
            data = json.loads(msg.value().decode("utf-8"))
            yield {
                "invoice_number":     data["invoice"]["number"],
                "invoice_date":       data["invoice"]["date"],
                "operator_id":        data["invoice"]["operator"],
                "store_name":         data["store"]["name"],
                "store_vat_id":       data["store"]["vat_id"],
                "store_address":      data["store"]["address"],
                "store_phone":        data["store"]["phone"],
                "total_amount":       float(data["totals"]["amount"]),
                "payment_method":     data["totals"]["payment_method"],
                "card_type":          data["totals"]["card_type"],
                "card_number_masked": data["totals"]["card_number"],
                "items_json":         json.dumps(data["items"]),
                "taxes_json":         json.dumps(data["taxes"]),
                "supermarket":        "MERCADONA",
                "_kafka_offset":      msg.offset(),
                "_ingested_at":       ingested_at,
                "_batch_timestamp":   data.get("batch_timestamp"),
            }
            consumer.commit(message=msg, asynchronous=False)
    finally:
        consumer.close()


def _exclusive_end(to_date: str) -> str:
    # A calendar date, not an instant: no timezone belongs on it, and adding one
    # would be an arbitrary choice. Parsed as a date so there is no naive datetime
    # to reason about at all.
    return (date.fromisoformat(to_date) + timedelta(days=1)).isoformat()


def _delete_stale_local(duckdb_path: str, from_date: str, to_date: str, batch_timestamp: str) -> None:
    """Remove rows in the [from_date, to_date] window that this run's Kafka batch didn't refresh.

    Kafka's merge write disposition only upserts by invoice_number, so an invoice that
    disappeared from the source (e.g. corrected/removed upstream) would otherwise never
    be removed from bronze. n8n re-publishes every invoice in the window on each run and
    stamps every message with the current DAG run's batch timestamp, so any row in the
    window that doesn't carry that timestamp after ingest is stale and can be dropped.
    Running this *after* the ingest (not before) means a failed/partial Kafka drain leaves
    existing data untouched instead of deleting it with nothing to replace it.
    """
    import duckdb

    con = duckdb.connect(duckdb_path)
    try:
        table_exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='bodega' AND table_name='raw_invoices'"
        ).fetchone()[0]
        if not table_exists:
            return
        con.execute(
            "DELETE FROM bodega.raw_invoices WHERE invoice_date >= ? AND invoice_date < ? "
            "AND (_batch_timestamp IS NULL OR _batch_timestamp != ?)",
            [from_date, _exclusive_end(to_date), batch_timestamp],
        )
    finally:
        con.close()


def _delete_stale_homelab(trino_url: str, from_date: str, to_date: str, batch_timestamp: str) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(trino_url)
    with engine.connect() as conn:
        try:
            conn.execute(
                text(
                    "DELETE FROM bronze.bodega.raw_invoices "
                    "WHERE invoice_date >= :from_date AND invoice_date < :to_date "
                    "AND (_batch_timestamp IS NULL OR _batch_timestamp != :batch_timestamp)"
                ),
                {"from_date": from_date, "to_date": _exclusive_end(to_date), "batch_timestamp": batch_timestamp},
            )
        except Exception:
            logger.debug("bronze.bodega.raw_invoices not found; skipping stale cleanup (first run?)", exc_info=True)


def run(target: str):
    config.validate_target(target)

    resource = raw_invoices(
        bootstrap_servers=config.kafka_bootstrap_servers(),
        topic=config.kafka_topic(),
    )

    from_date, to_date = config.ingest_from_date(), config.ingest_to_date()
    batch_timestamp = config.ingest_batch_timestamp()

    if target == "local":
        destination = dlt.destinations.duckdb(config.duckdb_path("bronze"))
    else:
        config.configure_iceberg_env("bronze")
        destination = dlt.destinations.filesystem(
            bucket_url=f"s3://{config.bronze_bucket()}",
            credentials=config.s3_credentials(),
        )
        resource.apply_hints(table_format="iceberg")

    pipeline = dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination=destination,
        dataset_name=DATASET_NAME,
    )
    load_info = pipeline.run(resource)
    row_counts = pipeline.last_trace.last_normalize_info.row_counts
    logger.info("%s: row counts %s", PIPELINE_NAME, row_counts)

    if row_counts.get(TABLE_NAME) and from_date and to_date and batch_timestamp:
        # Only reconcile if this run actually delivered fresh rows for the window — a run
        # with zero rows means nothing was republished (e.g. no fresh n8n batch, or a bare
        # ingest retry), not that the whole window disappeared. Cleaning up on a no-op run
        # would delete every previously-ingested row as "stale".
        if target == "local":
            _delete_stale_local(config.duckdb_path("bronze"), from_date, to_date, batch_timestamp)
        else:
            _delete_stale_homelab(config.trino_url(), from_date, to_date, batch_timestamp)

    return load_info
