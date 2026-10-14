"""Integration test: run the example_db pipeline against the local (DuckDB) target.

Seeds the bronze source table the dlt ingest would normally produce, runs `dbt build`
against DuckDB (one file per medallion catalog), then asserts the materialized tables.
No external services — but slower than the structural unit tests, so it is kept separate
and skipped by the fast suite.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Columns of the raw CSV (original hyphenated names), all strings — what the dlt ingest writes.
SOURCE_COLUMNS = [
    "symboling", "normalized-losses", "make", "fuel-type", "aspiration", "num-of-doors",
    "body-style", "drive-wheels", "engine-location", "wheel-base", "length", "width",
    "height", "curb-weight", "engine-type", "num-of-cylinders", "engine-size", "fuel-system",
    "bore", "stroke", "compression-ratio", "horsepower", "peak-rpm", "city-mpg",
    "highway-mpg", "price",
]
SAMPLE_ROWS = [
    ("3", "?", "alfa-romero", "gas", "std", "two", "convertible", "rwd", "front", "88.6",
     "168.8", "64.1", "48.8", "2548", "dohc", "four", "130", "mpfi", "3.47", "2.68", "9.0",
     "111", "5000", "21", "27", "13495"),
    ("1", "118", "audi", "gas", "std", "four", "sedan", "fwd", "front", "99.8", "176.6",
     "66.2", "54.3", "2337", "ohc", "four", "109", "mpfi", "3.19", "3.4", "10.0", "102",
     "5500", "24", "30", "13950"),
    ("2", "?", "  ", "gas", "std", "two", "hatchback", "fwd", "front", "93.7", "157.3",
     "63.8", "50.8", "1876", "ohc", "four", "92", "2bbl", "2.97", "3.23", "9.4", "68",
     "5500", "31", "38", "6855"),
]

PROJECT_DIR = Path(__file__).parent.parent.parent / "projects" / "example_db"


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    import duckdb

    tmp = tmp_path_factory.mktemp("dbt_integration")
    paths = {
        "DBT_DUCKDB_PATH": str(tmp / "bronze.duckdb"),
        "DBT_DUCKDB_SILVER_PATH": str(tmp / "silver.duckdb"),
        "DBT_DUCKDB_GOLD_PATH": str(tmp / "gold.duckdb"),
    }
    os.environ.update(paths)

    # Seed the bronze source the dlt ingest would normally create.
    cols = ", ".join(f'"{c}" VARCHAR' for c in SOURCE_COLUMNS)
    placeholders = ", ".join("?" for _ in SOURCE_COLUMNS)
    seed = duckdb.connect(paths["DBT_DUCKDB_PATH"])
    seed.execute("CREATE SCHEMA IF NOT EXISTS example_db")
    seed.execute(f"CREATE OR REPLACE TABLE example_db.automotive_source ({cols})")
    seed.executemany(
        f"INSERT INTO example_db.automotive_source VALUES ({placeholders})", SAMPLE_ROWS
    )
    seed.close()

    # Run dbt in a subprocess so its DuckDB instance is gone before verification — avoids
    # DuckDB's per-process "file already attached" conflicts when we re-open the catalogs.
    proc = subprocess.run(
        [sys.executable, "-m", "dbt_runner", "--project", "example_db",
         "--target", "local", "--full-refresh"],
        cwd=Path(__file__).parent.parent.parent,
        env={**os.environ},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

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


def test_source_has_rows(con):
    assert _count(con, "bronze.example_db.automotive_source") == len(SAMPLE_ROWS)


def test_snapshot_drops_empty_makes(con):
    # The blank-make row is filtered out by the snapshot model.
    assert _count(con, "bronze.example_db.automotive_snapshot") == len(SAMPLE_ROWS) - 1
    bad = con.execute(
        "SELECT COUNT(*) FROM bronze.example_db.automotive_snapshot "
        "WHERE make IS NULL OR TRIM(make) = ''"
    ).fetchone()[0]
    assert bad == 0


def test_snapshot_casts_numerics(con):
    row = con.execute(
        "SELECT MIN(city_mpg), MAX(highway_mpg) FROM bronze.example_db.automotive_snapshot"
    ).fetchone()
    assert row[0] > 0
    assert row[1] > row[0]


def test_raw_in_silver_catalog(con):
    assert _count(con, "silver.example_db.automotive_raw") > 0


def test_make_price_summary_aggregated(con):
    row = con.execute(
        "SELECT COUNT(DISTINCT make), MIN(avg_price) "
        "FROM gold.example_db.automotive_make_price_summary"
    ).fetchone()
    assert row[0] >= 1
    assert row[1] > 0


def test_fuel_body_mpg_summary_in_gold_catalog(con):
    assert _count(con, "gold.example_db.automotive_fuel_body_mpg_summary") > 0
