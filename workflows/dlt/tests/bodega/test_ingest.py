"""Unit tests for the bodega Kafka ingest resource.

No real Kafka connection — Consumer is mocked throughout.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

SAMPLE_INVOICE = {
    "invoice": {
        "number":   "4693-010-579596",
        "date":     "2025-07-16T09:31:00",
        "operator": "3436290",
    },
    "store": {
        "name":    "MERCADONA, S.A.",
        "vat_id":  "A-46103834",
        "address": "C/ TEST 1, 28001 MADRID",
        "phone":   "917578853",
    },
    "items": [
        {"description": "FILETE CABEZA LOMO", "quantity": 1,     "unit_price": 3.60, "total": 3.60},
        {"description": "PARAGUAYO",          "quantity": 0.886, "unit_price": 3.30, "total": 2.92},
    ],
    "totals": {
        "amount":         24.45,
        "payment_method": "TARJETA BANCARIA",
        "card_type":      "DEBIT MASTERCARD",
        "card_number":    "**** **** **** 6403",
    },
    "taxes": [
        {"rate": "4%",  "base": 8.38, "tax": 0.34},
        {"rate": "10%", "base": 8.16, "tax": 0.82},
    ],
}

INVOICE_2 = {**SAMPLE_INVOICE, "invoice": {**SAMPLE_INVOICE["invoice"], "number": "0001-001-000001"}}


def _make_msg(invoice_dict, offset=0, error=None):
    msg = MagicMock()
    msg.error.return_value = error
    msg.value.return_value = json.dumps(invoice_dict).encode("utf-8")
    msg.offset.return_value = offset
    return msg


def _collect(poll_responses):
    """Run raw_invoices with a mocked Consumer and return yielded records."""
    with patch("bodega.ingest.Consumer") as MockConsumer:
        consumer = MockConsumer.return_value
        consumer.poll.side_effect = poll_responses
        from bodega.ingest import raw_invoices
        return list(raw_invoices("server:9093", "bodega_invoices")), consumer


class TestRawInvoicesFlattening:
    def test_yields_one_record_per_message(self):
        records, _ = _collect([_make_msg(SAMPLE_INVOICE), None, None, None])
        assert len(records) == 1

    def test_flattens_invoice_fields(self):
        records, _ = _collect([_make_msg(SAMPLE_INVOICE), None, None, None])
        r = records[0]
        assert r["invoice_number"] == "4693-010-579596"
        assert r["invoice_date"] == "2025-07-16T09:31:00"
        assert r["operator_id"] == "3436290"

    def test_flattens_store_fields(self):
        records, _ = _collect([_make_msg(SAMPLE_INVOICE), None, None, None])
        r = records[0]
        assert r["store_name"] == "MERCADONA, S.A."
        assert r["store_vat_id"] == "A-46103834"
        assert r["store_address"] == "C/ TEST 1, 28001 MADRID"
        assert r["store_phone"] == "917578853"

    def test_flattens_totals_fields(self):
        records, _ = _collect([_make_msg(SAMPLE_INVOICE), None, None, None])
        r = records[0]
        assert r["total_amount"] == 24.45
        assert r["payment_method"] == "TARJETA BANCARIA"
        assert r["card_type"] == "DEBIT MASTERCARD"
        assert r["card_number_masked"] == "**** **** **** 6403"

    def test_supermarket_hardcoded(self):
        records, _ = _collect([_make_msg(SAMPLE_INVOICE), None, None, None])
        assert records[0]["supermarket"] == "MERCADONA"

    def test_items_stored_as_json_string(self):
        records, _ = _collect([_make_msg(SAMPLE_INVOICE), None, None, None])
        items = json.loads(records[0]["items_json"])
        assert len(items) == 2
        assert items[0]["description"] == "FILETE CABEZA LOMO"
        assert items[1]["quantity"] == 0.886

    def test_taxes_stored_as_json_string(self):
        records, _ = _collect([_make_msg(SAMPLE_INVOICE), None, None, None])
        taxes = json.loads(records[0]["taxes_json"])
        assert len(taxes) == 2
        assert taxes[0]["rate"] == "4%"
        assert taxes[1]["base"] == 8.16

    def test_kafka_offset_stored(self):
        records, _ = _collect([_make_msg(SAMPLE_INVOICE, offset=42), None, None, None])
        assert records[0]["_kafka_offset"] == 42

    def test_batch_timestamp_stored(self):
        invoice = {**SAMPLE_INVOICE, "batch_timestamp": "2026-07-05T08:00:00+00:00"}
        records, _ = _collect([_make_msg(invoice), None, None, None])
        assert records[0]["_batch_timestamp"] == "2026-07-05T08:00:00+00:00"

    def test_batch_timestamp_defaults_to_none_when_missing(self):
        records, _ = _collect([_make_msg(SAMPLE_INVOICE), None, None, None])
        assert records[0]["_batch_timestamp"] is None


class TestRawInvoicesKafkaBehaviour:
    def test_stops_after_three_consecutive_idle_polls(self):
        msg = _make_msg(SAMPLE_INVOICE)
        records, consumer = _collect([msg, None, None, None])
        # Poll called 4 times: 1 message + 3 Nones
        assert consumer.poll.call_count == 4
        assert len(records) == 1

    def test_yields_multiple_messages(self):
        m1 = _make_msg(SAMPLE_INVOICE, offset=0)
        m2 = _make_msg(INVOICE_2, offset=1)
        records, _ = _collect([m1, m2, None, None, None])
        assert len(records) == 2
        assert records[0]["invoice_number"] == "4693-010-579596"
        assert records[1]["invoice_number"] == "0001-001-000001"

    def test_idle_counter_resets_after_a_message(self):
        m1 = _make_msg(SAMPLE_INVOICE, offset=0)
        m2 = _make_msg(INVOICE_2, offset=1)
        # Two idle then message resets counter, then 3 more idle to stop
        records, _ = _collect([None, None, m1, None, m2, None, None, None])
        assert len(records) == 2

    def test_consumer_committed_after_each_message(self):
        m1 = _make_msg(SAMPLE_INVOICE, offset=0)
        m2 = _make_msg(INVOICE_2, offset=1)
        _, consumer = _collect([m1, m2, None, None, None])
        assert consumer.commit.call_count == 2
        consumer.commit.assert_any_call(message=m1, asynchronous=False)
        consumer.commit.assert_any_call(message=m2, asynchronous=False)

    def test_consumer_closed_on_completion(self):
        _, consumer = _collect([_make_msg(SAMPLE_INVOICE), None, None, None])
        consumer.close.assert_called_once()

    def test_consumer_closed_on_exception(self):
        # dlt wraps generator exceptions in ResourceExtractionError; the finally
        # block still runs (CPython reference counting drops the generator immediately).
        from dlt.extract.exceptions import ResourceExtractionError

        with patch("bodega.ingest.Consumer") as MockConsumer:
            consumer = MockConsumer.return_value
            consumer.poll.side_effect = RuntimeError("network error")
            from bodega.ingest import raw_invoices
            with pytest.raises(ResourceExtractionError):
                list(raw_invoices("server:9093", "bodega_invoices"))
        consumer.close.assert_called_once()

    def test_eof_error_stops_polling(self):
        from confluent_kafka import KafkaError

        eof_error = MagicMock()
        eof_error.code.return_value = KafkaError._PARTITION_EOF
        eof_msg = MagicMock()
        eof_msg.error.return_value = eof_error

        records, _ = _collect([_make_msg(SAMPLE_INVOICE), eof_msg])
        assert len(records) == 1


class TestDeleteStaleLocal:
    def test_noop_when_table_missing(self, tmp_path):
        import duckdb

        db = tmp_path / "bronze.duckdb"
        duckdb.connect(str(db)).close()

        from bodega.ingest import _delete_stale_local
        _delete_stale_local(str(db), "2025-07-01", "2025-07-31", "batch-1")  # should not raise

    def test_deletes_only_stale_rows_within_window(self, tmp_path):
        import duckdb

        db = tmp_path / "bronze.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA bodega")
        con.execute(
            "CREATE TABLE bodega.raw_invoices AS SELECT * FROM (VALUES "
            "('REFRESHED', '2025-07-16T09:31:00', 'batch-1'), "
            "('STALE', '2025-07-17T09:31:00', 'batch-0'), "
            "('LEGACY-UNTAGGED', '2025-07-18T09:31:00', NULL), "
            "('BEFORE', '2025-06-30T23:59:59', 'batch-0'), "
            "('ON-BOUNDARY', '2025-08-01T00:00:00', 'batch-0'), "
            "('AFTER', '2025-08-02T00:00:00', 'batch-0')"
            ") t(invoice_number, invoice_date, _batch_timestamp)"
        )
        con.close()

        from bodega.ingest import _delete_stale_local
        _delete_stale_local(str(db), "2025-07-01", "2025-07-31", "batch-1")

        con = duckdb.connect(str(db))
        remaining = {r[0] for r in con.execute("SELECT invoice_number FROM bodega.raw_invoices").fetchall()}
        con.close()
        assert remaining == {"REFRESHED", "BEFORE", "ON-BOUNDARY", "AFTER"}


class TestDeleteStaleHomelab:
    def test_swallows_missing_table_error(self):
        from bodega.ingest import _delete_stale_homelab

        with patch("sqlalchemy.create_engine") as mock_create_engine:
            conn = mock_create_engine.return_value.connect.return_value.__enter__.return_value
            conn.execute.side_effect = RuntimeError("table not found")
            _delete_stale_homelab("trino://dbt@host:8080", "2025-07-01", "2025-07-31", "batch-1")  # should not raise

    def test_issues_delete_with_exclusive_end_date_and_batch_timestamp(self):
        from bodega.ingest import _delete_stale_homelab

        with patch("sqlalchemy.create_engine") as mock_create_engine:
            conn = mock_create_engine.return_value.connect.return_value.__enter__.return_value
            _delete_stale_homelab("trino://dbt@host:8080", "2025-07-01", "2025-07-31", "batch-1")
            params = conn.execute.call_args.args[1]
            assert params == {"from_date": "2025-07-01", "to_date": "2025-08-01", "batch_timestamp": "batch-1"}


class TestRunStaleCleanupGuard:
    """A run that ingests zero rows must not trigger the stale-window cleanup —
    otherwise a bare retry (no fresh n8n batch) would delete every valid row in the
    window, since none of them carry the new run's batch timestamp."""

    def _run(self, tmp_path, monkeypatch, poll_responses):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "server:9093")
        monkeypatch.setenv("DBT_DUCKDB_DIR", str(tmp_path))
        monkeypatch.setenv("BODEGA_FROM_DATE", "2025-07-01")
        monkeypatch.setenv("BODEGA_TO_DATE", "2025-07-31")
        monkeypatch.setenv("BODEGA_BATCH_TIMESTAMP", "batch-1")

        with patch("bodega.ingest.Consumer") as MockConsumer, \
             patch("bodega.ingest._delete_stale_local") as mock_delete:
            MockConsumer.return_value.poll.side_effect = poll_responses
            from bodega import ingest
            ingest.run("local")
        return mock_delete

    def test_skips_cleanup_when_zero_rows_ingested(self, tmp_path, monkeypatch):
        mock_delete = self._run(tmp_path, monkeypatch, [None, None, None])
        mock_delete.assert_not_called()

    def test_runs_cleanup_when_rows_ingested(self, tmp_path, monkeypatch):
        mock_delete = self._run(tmp_path, monkeypatch, [_make_msg(SAMPLE_INVOICE), None, None, None])
        mock_delete.assert_called_once_with(
            str(tmp_path / "bronze.duckdb"), "2025-07-01", "2025-07-31", "batch-1"
        )
