"""Validate bodega dbt project + profile structure without a warehouse connection."""
from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).parent.parent.parent / "projects" / "bodega"


def _load(name: str) -> dict:
    return yaml.safe_load((PROJECT_DIR / name).read_text())


class TestBodegaProfiles:
    def setup_method(self):
        self.profile = _load("profiles.yml")["bodega"]

    def test_default_target_is_homelab(self):
        assert self.profile["target"] == "homelab"

    def test_homelab_and_local_targets_defined(self):
        assert set(self.profile["outputs"]) == {"homelab", "local"}

    def test_homelab_uses_trino_local_uses_duckdb(self):
        assert self.profile["outputs"]["homelab"]["type"] == "trino"
        assert self.profile["outputs"]["local"]["type"] == "duckdb"

    def test_local_attaches_silver_and_gold_databases(self):
        aliases = {a["alias"] for a in self.profile["outputs"]["local"]["attach"]}
        assert "silver" in aliases
        assert "gold" in aliases


class TestBodegaProject:
    def setup_method(self):
        self.project = _load("dbt_project.yml")
        self.models = self.project["models"]["bodega"]

    def test_models_materialized_as_tables(self):
        assert self.models["+materialized"] == "table"

    def test_medallion_layers_target_their_catalogs(self):
        assert self.models["+schema"] == "bodega"
        assert self.models["silver"]["+database"] == "silver"
        assert self.models["gold"]["+database"] == "gold"

    def test_generate_schema_name_macro_present(self):
        macro = PROJECT_DIR / "macros" / "generate_schema_name.sql"
        assert macro.exists()
        assert "custom_schema_name" in macro.read_text()


class TestBodegaSources:
    def setup_method(self):
        self.sources = {s["name"]: s for s in _load("models/sources.yml")["sources"]}

    def test_raw_invoices_source_in_bronze_catalog(self):
        src = self.sources["bodega"]
        assert src["database"] == "bronze"
        assert src["schema"] == "bodega"
        assert any(t["name"] == "raw_invoices" for t in src["tables"])

    def test_products_enrich_source_in_silver_catalog(self):
        src = self.sources["bodega_enrich"]
        assert src["database"] == "silver"
        assert src["schema"] == "bodega"
        assert any(t["name"] == "products" for t in src["tables"])


def test_project_parses():
    """dbt parse validates refs/sources/macros without a warehouse connection."""
    from dbt.cli.main import dbtRunner

    result = dbtRunner().invoke([
        "parse",
        "--project-dir", str(PROJECT_DIR),
        "--profiles-dir", str(PROJECT_DIR),
        "--target", "local",
    ])
    assert result.success, getattr(result, "exception", "dbt parse failed")


class TestPersistDocs:
    """`persist_docs` is load-bearing: the semantic MCP server reads column docs
    from Iceberg comments, so an undocumented column and one with an empty
    description are indistinguishable to it (both land as a NULL comment).
    """

    def setup_method(self):
        self.project = _load("dbt_project.yml")
        self.schema = _load("models/schema.yml")

    def test_persist_docs_enabled_for_relations_and_columns(self):
        config = self.project["models"]["bodega"]["+persist_docs"]
        assert config == {"relation": True, "columns": True}

    def test_every_documented_column_has_a_description(self):
        missing = [
            f"{model['name']}.{column['name']}"
            for model in self.schema["models"]
            for column in model.get("columns") or []
            if not (column.get("description") or "").strip()
        ]
        assert not missing, (
            f"these columns are listed in schema.yml with no description, so dbt "
            f"writes a NULL Iceberg comment and the semantic registry reads them "
            f"as undocumented: {', '.join(missing)}"
        )

    def test_every_model_has_a_description(self):
        missing = [
            model["name"]
            for model in self.schema["models"]
            if not (model.get("description") or "").strip()
        ]
        assert not missing, f"models with no description: {', '.join(missing)}"
