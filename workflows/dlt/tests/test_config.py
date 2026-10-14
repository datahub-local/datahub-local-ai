"""Unit tests for dlt_runner config helpers — no pipeline run required.

Shared infrastructure (Trino, Polaris, DuckDB, S3) is tested against ``dlt_runner.config``.
Pipeline-specific config (EXPORTS, Postgres DSN, export paths) is tested against ``example_db.config``.
"""
import os

from example_db import config

from dlt_runner import config as shared_config


class TestCatalogMapping:
    def test_medallion_catalogs_map_to_polaris_catalogs(self):
        assert config.CATALOG_WAREHOUSES["bronze"] == "bronze"
        assert config.CATALOG_WAREHOUSES["silver"] == "silver"
        assert config.CATALOG_WAREHOUSES["gold"] == "gold"
        assert config.CATALOG_WAREHOUSES["test"] == "test"

    def test_exports_cover_silver_and_gold_tables(self):
        assert config.EXPORTS[("silver", "example_db", "automotive_raw")] == "automotive_raw"
        assert config.EXPORTS[("gold", "example_db", "automotive_make_price_summary")] == \
            "automotive_make_price_summary"
        assert config.EXPORTS[("gold", "example_db", "automotive_fuel_body_mpg_summary")] == \
            "automotive_fuel_body_mpg_summary"


class TestDuckdbPaths:
    def test_duckdb_path_uses_dbt_env_vars(self, monkeypatch):
        monkeypatch.setenv("DBT_DUCKDB_PATH", "/data/bronze.duckdb")
        assert shared_config.duckdb_path("bronze") == "/data/bronze.duckdb"

    def test_duckdb_path_default_matches_catalog_name(self, monkeypatch):
        monkeypatch.delenv("DBT_DUCKDB_GOLD_PATH", raising=False)
        monkeypatch.setenv("DBT_DUCKDB_DIR", "/wh")
        assert shared_config.duckdb_path("gold") == "/wh/gold.duckdb"


class TestTempBucket:
    def test_default_temp_bucket(self, monkeypatch):
        monkeypatch.delenv("DLT_TEMP_BUCKET", raising=False)
        assert shared_config.temp_bucket() == "datahub-local-temp"


class TestSilverBucket:
    def test_default_silver_bucket(self, monkeypatch):
        monkeypatch.delenv("DLT_SILVER_BUCKET", raising=False)
        assert shared_config.silver_bucket() == "datahub-local-silver"


class TestPostgresDsn:
    def test_builds_dsn_from_jdbc_url(self, monkeypatch):
        monkeypatch.delenv("EXAMPLE_DB_DSN", raising=False)
        monkeypatch.setenv("EXAMPLE_DB_URL", "jdbc:postgresql://pg-host:5432/dbt")
        monkeypatch.setenv("EXAMPLE_DB_USER", "pguser")
        monkeypatch.setenv("EXAMPLE_DB_PASSWORD", "secret")
        assert config.postgres_dsn() == "postgresql://pguser:secret@pg-host:5432/dbt"

    def test_explicit_dsn_wins(self, monkeypatch):
        monkeypatch.setenv("EXAMPLE_DB_DSN", "postgresql://u:p@h/db")
        assert config.postgres_dsn() == "postgresql://u:p@h/db"


class TestIcebergEnv:
    def test_configure_iceberg_env_sets_rest_catalog(self, monkeypatch):
        for key in list(os.environ):
            if key.startswith("PYICEBERG_CATALOG__BRONZE__"):
                monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("ICEBERG_CATALOG_URI", "http://polaris/api/catalog")
        shared_config.configure_iceberg_env("bronze")
        assert os.environ["PYICEBERG_CATALOG__BRONZE__TYPE"] == "rest"
        assert os.environ["PYICEBERG_CATALOG__BRONZE__URI"] == "http://polaris/api/catalog"
        assert os.environ["PYICEBERG_CATALOG__BRONZE__WAREHOUSE"] == "bronze"

    def test_configure_iceberg_env_custom_warehouse(self, monkeypatch):
        for key in list(os.environ):
            if key.startswith("PYICEBERG_CATALOG__BRONZE__"):
                monkeypatch.delenv(key, raising=False)
        shared_config.configure_iceberg_env("bronze", warehouse="my-polaris-catalog")
        assert os.environ["PYICEBERG_CATALOG__BRONZE__WAREHOUSE"] == "my-polaris-catalog"

    def test_configure_iceberg_env_sets_dlt_catalog_name(self, monkeypatch):
        # dlt resolves the iceberg catalog name from this var; it must match the
        # PYICEBERG_CATALOG__<CATALOG>__* prefix or dlt looks for a "default" catalog.
        monkeypatch.delenv("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME", raising=False)
        shared_config.configure_iceberg_env("silver")
        assert os.environ["ICEBERG_CATALOG__ICEBERG_CATALOG_NAME"] == "silver"

    def test_configure_iceberg_env_sets_credential(self, monkeypatch):
        for key in list(os.environ):
            if key.startswith("PYICEBERG_CATALOG__BRONZE__"):
                monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("POLARIS_CREDENTIAL", "myid:mysecret")
        monkeypatch.delenv("POLARIS_TOKEN", raising=False)
        shared_config.configure_iceberg_env("bronze")
        assert os.environ["PYICEBERG_CATALOG__BRONZE__CREDENTIAL"] == "myid:mysecret"
        assert "PYICEBERG_CATALOG__BRONZE__TOKEN" not in os.environ

    def test_configure_iceberg_env_sets_token_when_no_credential(self, monkeypatch):
        for key in list(os.environ):
            if key.startswith("PYICEBERG_CATALOG__BRONZE__"):
                monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv("POLARIS_CREDENTIAL", raising=False)
        monkeypatch.setenv("POLARIS_TOKEN", "mytoken")
        shared_config.configure_iceberg_env("bronze")
        assert os.environ["PYICEBERG_CATALOG__BRONZE__TOKEN"] == "mytoken"
        assert "PYICEBERG_CATALOG__BRONZE__CREDENTIAL" not in os.environ

    def test_configure_iceberg_env_no_auth_sets_no_credential_or_token(self, monkeypatch):
        for key in list(os.environ):
            if key.startswith("PYICEBERG_CATALOG__BRONZE__"):
                monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv("POLARIS_CREDENTIAL", raising=False)
        monkeypatch.delenv("POLARIS_TOKEN", raising=False)
        shared_config.configure_iceberg_env("bronze")
        assert "PYICEBERG_CATALOG__BRONZE__CREDENTIAL" not in os.environ
        assert "PYICEBERG_CATALOG__BRONZE__TOKEN" not in os.environ


class TestTrinoUrl:
    def test_trino_url_defaults(self, monkeypatch):
        for key in ("TRINO_HOST", "TRINO_PORT", "TRINO_USER"):
            monkeypatch.delenv(key, raising=False)
        assert shared_config.trino_url() == "trino://dbt@datahub-local-core-data-trino-trino:8080"
