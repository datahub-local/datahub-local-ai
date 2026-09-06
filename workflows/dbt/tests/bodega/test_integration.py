"""Integration test: run the bodega pipeline against the local (DuckDB) target.

Mirrors the production order (dlt ingest → dbt silver → dlt enrich → dbt gold) with the
two dlt steps replaced by direct seeds: it seeds the bronze ``raw_invoices`` table the dlt
ingest would produce, runs ``dbt build --select silver.*``, seeds the ``products`` table the
dlt enrich step would produce, then runs ``dbt build --select gold.*`` and asserts the
materialized medallion tables. No external services — proves the Trino-authored SQL also
runs on DuckDB via the cross_engine macros.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Columns the dlt ingest writes into bronze.bodega.raw_invoices.
RAW_COLUMNS = [
    "invoice_number", "invoice_date", "operator_id", "store_name", "store_vat_id",
    "store_address", "store_phone", "total_amount", "payment_method", "card_type",
    "card_number_masked", "items_json", "taxes_json", "supermarket", "_kafka_offset",
    "_ingested_at",
]

_INV1 = (
    "INV-1", "2026-01-15T18:30:00", "OP1", "Mercadona Centro", "B12345678",
    "C/ Mayor 1", "900111222", 2.90, "CARD", "VISA", "**** **** **** 1234",
    json.dumps([
        {"description": "Leche Entera", "quantity": "2",   "unit_price": "0.85", "total": "1.70"},
        {"description": "Pan Integral", "quantity": "1",   "unit_price": "1.20", "total": "1.20"},
    ]),
    json.dumps([{"rate": "10%", "base": "2.64", "tax": "0.26"}]),
    "MERCADONA", 0, "2026-01-15T18:31:00+00:00",
)
# Same store as INV-1 but with raw formatting variants (name casing, address spelling):
# the stores model must still collapse both invoices into one row per VAT ID.
_INV2 = (
    "INV-2", "2026-01-16T10:00:00", "OP1", "MERCADONA CENTRO ", "B12345678",
    "Calle Mayor, 1", "900111222", 5.25, "CASH", None, None,
    json.dumps([
        {"description": "Leche Entera",   "quantity": "3",   "unit_price": "0.85", "total": "2.55"},
        {"description": "Manzana Golden", "quantity": "1.5", "unit_price": "1.80", "total": "2.70"},
    ]),
    json.dumps([{"rate": "4%", "base": "5.05", "tax": "0.20"}]),
    "MERCADONA", 1, "2026-01-16T10:01:00+00:00",
)
# A second store, whose address carries a postal code and an accented town: exercises
# the address parse, the accent stripping, and (against _INV1/_INV2, whose address has
# no postal code and so lands in UNKNOWN) that both kinds keep their spend in a total.
_INV3 = (
    "INV-3", "2026-01-17T12:00:00", "OP2", "Mercadona Test Dos", "B99999999",
    "C/ TEST 2, 03700 TESTV\u00cdLA", "900333444", 4.00, "CARD", "VISA", "**** **** **** 9999",
    json.dumps([
        {"description": "Leche Entera", "quantity": "1", "unit_price": "0.85", "total": "0.85"},
    ]),
    json.dumps([{"rate": "4%", "base": "3.85", "tax": "0.15"}]),
    "MERCADONA", 2, "2026-01-17T12:01:00+00:00",
)
RAW_ROWS = [_INV1, _INV2, _INV3]

# Product dimension the dlt enrich step would categorise (silver.bodega.products).
# LECHE ENTERA appears twice (the Iceberg filesystem destination downgrades dlt's
# merge to append): the gold models must dedupe to the latest categorized_at row
# without fanning out the joined invoice lines.
PRODUCT_COLUMNS = ["description_clean", "supermarket", "category", "subcategory", "is_weighted", "categorized_at"]
PRODUCT_ROWS = [
    ("LECHE ENTERA",   "MERCADONA", "OTHER",             "PARSE_ERROR", False, "2026-01-16T00:00:00+00:00"),
    ("LECHE ENTERA",   "MERCADONA", "DAIRY_EGGS",        "Milk",  False, "2026-01-17T00:00:00+00:00"),
    ("PAN INTEGRAL",   "MERCADONA", "BAKERY_PASTRY",     "Bread", False, "2026-01-17T00:00:00+00:00"),
    ("MANZANA GOLDEN", "MERCADONA", "FRUITS_VEGETABLES", "Apple", True,  "2026-01-17T00:00:00+00:00"),
]

ROOT = Path(__file__).parent.parent.parent


def _dbt_build(select: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "dbt_runner", "--project", "bodega",
         "--target", "local", "--select", select, "--full-refresh"],
        cwd=ROOT,
        env={**os.environ},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    import duckdb

    tmp = tmp_path_factory.mktemp("dbt_bodega_integration")
    paths = {
        "DBT_DUCKDB_PATH": str(tmp / "bronze.duckdb"),
        "DBT_DUCKDB_SILVER_PATH": str(tmp / "silver.duckdb"),
        "DBT_DUCKDB_GOLD_PATH": str(tmp / "gold.duckdb"),
    }
    os.environ.update(paths)

    # 1. Seed the bronze source the dlt ingest would create.
    cols = ", ".join(
        f'"{c}" ' + ("DOUBLE" if c == "total_amount" else "BIGINT" if c == "_kafka_offset" else "VARCHAR")
        for c in RAW_COLUMNS
    )
    placeholders = ", ".join("?" for _ in RAW_COLUMNS)
    bronze = duckdb.connect(paths["DBT_DUCKDB_PATH"])
    bronze.execute("CREATE SCHEMA IF NOT EXISTS bodega")
    bronze.execute(f"CREATE OR REPLACE TABLE bodega.raw_invoices ({cols})")
    bronze.executemany(f"INSERT INTO bodega.raw_invoices VALUES ({placeholders})", RAW_ROWS)
    bronze.close()

    # 2. Build the silver layer (in its own process — DuckDB single-writer per file).
    _dbt_build("silver.*")

    # 3. Seed the product dimension the dlt enrich step would create.
    p_cols = ", ".join(f'"{c}" ' + ("BOOLEAN" if c == "is_weighted" else "VARCHAR") for c in PRODUCT_COLUMNS)
    p_ph = ", ".join("?" for _ in PRODUCT_COLUMNS)
    silver = duckdb.connect(paths["DBT_DUCKDB_SILVER_PATH"])
    silver.execute("CREATE SCHEMA IF NOT EXISTS bodega")
    silver.execute(f"CREATE OR REPLACE TABLE bodega.products ({p_cols})")
    silver.executemany(f"INSERT INTO bodega.products VALUES ({p_ph})", PRODUCT_ROWS)
    silver.close()

    # 4. Build the gold layer.
    _dbt_build("gold.*")

    yield paths


@pytest.fixture(scope="module")
def con(warehouse):
    import duckdb

    verify = duckdb.connect(warehouse["DBT_DUCKDB_PATH"], read_only=True)
    verify.execute(f"ATTACH '{warehouse['DBT_DUCKDB_SILVER_PATH']}' AS silver (READ_ONLY)")
    verify.execute(f"ATTACH '{warehouse['DBT_DUCKDB_GOLD_PATH']}' AS gold (READ_ONLY)")
    yield verify
    verify.close()


def _count(con, table: str) -> int:
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_silver_invoices_one_row_per_invoice(con):
    assert _count(con, "silver.bodega.invoices") == len(RAW_ROWS)


def test_silver_invoices_computes_tax_from_json(con):
    tax = con.execute(
        "SELECT total_tax_amount FROM silver.bodega.invoices WHERE invoice_number = 'INV-1'"
    ).fetchone()[0]
    assert tax == pytest.approx(0.26)


def test_silver_invoices_item_count_from_json(con):
    counts = con.execute(
        "SELECT invoice_number, item_count FROM silver.bodega.invoices ORDER BY invoice_number"
    ).fetchall()
    assert counts == [("INV-1", 2), ("INV-2", 2), ("INV-3", 1)]


def test_silver_invoice_items_exploded_with_position(con):
    assert _count(con, "silver.bodega.invoice_items") == 5
    positions = con.execute(
        "SELECT DISTINCT item_position FROM silver.bodega.invoice_items ORDER BY item_position"
    ).fetchall()
    assert positions == [(1,), (2,)]


def test_silver_invoice_items_derives_unit(con):
    # quantity 1.5 (Manzana) is fractional -> KG; whole quantities -> EA.
    unit = con.execute(
        "SELECT unit FROM silver.bodega.invoice_items WHERE description_clean = 'MANZANA GOLDEN'"
    ).fetchone()[0]
    assert unit == "KG"


def test_silver_invoice_taxes_exploded(con):
    assert _count(con, "silver.bodega.invoice_taxes") == 3


def test_silver_stores_dedups_by_vat(con):
    assert _count(con, "silver.bodega.stores") == 2


def test_silver_stores_latest_invoice_wins(con):
    # INV-2 is the most recent invoice, so its descriptive fields win.
    row = con.execute(
        "SELECT name, address, first_seen_date, last_seen_date FROM silver.bodega.stores"
        " WHERE store_id = 'B12345678'"
    ).fetchone()
    assert row[0] == "MERCADONA CENTRO"
    assert row[1] == "Calle Mayor, 1"
    assert str(row[2]) == "2026-01-15"
    assert str(row[3]) == "2026-01-16"


def test_gold_top_products_joins_categories(con):
    rows = con.execute(
        "SELECT description_clean, category FROM gold.bodega.top_products ORDER BY description_clean"
    ).fetchall()
    assert ("LECHE ENTERA", "DAIRY_EGGS") in rows
    assert len(rows) == 3


def test_gold_top_products_dedupes_product_dimension(con):
    # The duplicated LECHE ENTERA product row must neither fan out the join
    # (inflating spend) nor win with its stale PARSE_ERROR categorisation.
    count, spent = con.execute(
        "SELECT COUNT(*), SUM(total_spent) FROM gold.bodega.top_products"
        " WHERE description_clean = 'LECHE ENTERA'"
    ).fetchone()
    assert count == 1
    assert spent == pytest.approx(1.70 + 2.55 + 0.85)


def test_gold_price_trends_keeps_only_repeat_products(con):
    # Only Leche Entera is bought in both invoices (>= 2 line items).
    products = {r[0] for r in con.execute(
        "SELECT DISTINCT description_clean FROM gold.bodega.price_trends"
    ).fetchall()}
    assert products == {"LECHE ENTERA"}


def test_gold_price_trends_blended_price(con):
    # price = total spent / total quantity: (1.70 + 2.55) / (2 + 3) = 0.85 €/unit.
    row = con.execute(
        "SELECT price, is_weighted FROM gold.bodega.price_trends WHERE description_clean = 'LECHE ENTERA'"
    ).fetchone()
    assert row[0] == pytest.approx(0.85)
    assert row[1] is False


def test_gold_category_spending_in_gold_catalog(con):
    assert _count(con, "gold.bodega.category_spending") > 0


def test_gold_tax_summary_sums_by_month(con):
    assert _count(con, "gold.bodega.tax_summary") == 2


class TestLocationParsing:
    """Postal code, province and town parsed out of the free-text store address.

    The two stores are deliberately different shapes: B99999999's address carries a
    postal code and an accented town, B12345678's carries neither.
    """

    def test_parses_postal_code_province_and_town(self, con):
        row = con.execute(
            "SELECT postal_code, province_code, province, town_raw, town"
            " FROM silver.bodega.stores WHERE store_id = 'B99999999'"
        ).fetchone()
        assert row == ("03700", "03", "Alicante/Alacant", "TESTVÍLA", "TESTVILA")

    def test_unparseable_address_is_unknown_not_null(self, con):
        # NULL would drop the row from a grouped query; UNKNOWN keeps it visible.
        row = con.execute(
            "SELECT postal_code, province_code, province, town_raw, town"
            " FROM silver.bodega.stores WHERE store_id = 'B12345678'"
        ).fetchone()
        assert row == ("UNKNOWN",) * 5

    def test_town_is_unaccented_for_filtering(self, con):
        # The semantic layer's near-miss suggester is skipped for `contains`, so a
        # wrong-accent filter would return zero rows and read as "no spend there".
        assert con.execute(
            "SELECT COUNT(*) FROM silver.bodega.stores WHERE town = 'TESTVILA'"
        ).fetchone()[0] == 1

    @pytest.mark.parametrize("table", ["invoices", "invoice_items"])
    def test_location_denormalised_onto_metric_models(self, con, table):
        # A semantic dimension must be a bare column on the metric's own model.
        rows = dict(con.execute(
            f"SELECT store_vat_id, MAX(store_town) FROM silver.bodega.{table}"
            " GROUP BY store_vat_id"
        ).fetchall())
        assert rows == {"B12345678": "UNKNOWN", "B99999999": "TESTVILA"}

    @pytest.mark.parametrize(
        "table,amount",
        [("invoices", "total_amount"), ("invoice_items", "total_amount")],
    )
    @pytest.mark.parametrize("dimension", ["store_province", "store_town", "store_postal_code"])
    def test_grouped_total_equals_ungrouped_total(self, con, table, amount, dimension):
        """L4: no spend is lost to a location breakdown, including the UNKNOWN bucket."""
        ungrouped = con.execute(f"SELECT SUM({amount}) FROM silver.bodega.{table}").fetchone()[0]
        grouped = con.execute(
            f"SELECT SUM(s) FROM (SELECT SUM({amount}) AS s FROM silver.bodega.{table}"
            f" GROUP BY {dimension}) AS g"
        ).fetchone()[0]
        assert grouped == pytest.approx(ungrouped)
