"""Unit tests for the bodega LLM enrichment pipeline.

No real Trino, DuckDB, or OpenRouter calls — all external dependencies are mocked.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestCategorizeBatch:
    def _call(self, descriptions, api_response):
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps(api_response)}}]
            }
            from bodega.enrich import _categorize_batch
            return _categorize_batch(descriptions, base_url="https://example.com/v1", api_key="test-key", model_id="test-model")

    def test_returns_one_result_per_description(self):
        descs = ["FILETE CABEZA LOMO", "PARAGUAYO"]
        api_resp = [
            {"category": "MEAT_FISH", "subcategory": "Pork", "is_weighted": False},
            {"category": "FRUITS_VEGETABLES", "subcategory": "Stone fruit", "is_weighted": True},
        ]
        results = self._call(descs, api_resp)
        assert len(results) == 2
        assert results[0]["category"] == "MEAT_FISH"
        assert results[1]["category"] == "FRUITS_VEGETABLES"

    def test_handles_wrapped_items_key(self):
        descs = ["LECHE ENTERA"]
        api_resp = {"items": [{"category": "DAIRY_EGGS", "subcategory": "Milk", "is_weighted": False}]}
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps(api_resp)}}]
            }
            from bodega.enrich import _categorize_batch
            results = _categorize_batch(descs, base_url="https://example.com/v1", api_key="k", model_id="m")
        assert results[0]["category"] == "DAIRY_EGGS"

    def test_falls_back_to_other_on_network_error(self):
        with patch("dlt_runner.llm.httpx.post", side_effect=Exception("network")):
            from bodega.enrich import _categorize_batch
            results = _categorize_batch(["PRODUCTO X"], base_url="https://example.com/v1", api_key="k", model_id="m")
        assert results[0]["category"] == "OTHER"
        assert results[0]["subcategory"] == "PARSE_ERROR"

    def test_falls_back_to_other_on_count_mismatch(self):
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            # API returns fewer items than descriptions
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps([{"category": "OTHER"}])}}]
            }
            from bodega.enrich import _categorize_batch
            results = _categorize_batch(["DESC_A", "DESC_B"], base_url="https://example.com/v1", api_key="k", model_id="m")
        assert all(r["category"] == "OTHER" for r in results)

    def test_ollama_sends_no_auth_header(self):
        """Empty api_key (Ollama default) must not send an Authorization header."""
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps([{"category": "OTHER", "subcategory": "", "is_weighted": False}])}}]
            }
            from bodega.enrich import _categorize_batch
            _categorize_batch(["X"], base_url="http://datahub-local-core-data-ollama:11434/v1", api_key="", model_id="lfm2.5-thinking:1.2b")
        headers = mock_post.call_args.kwargs["headers"]
        assert "Authorization" not in headers

    def test_openrouter_sends_bearer_token(self):
        """Non-empty api_key (OpenRouter) must include Authorization header."""
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps([{"category": "OTHER", "subcategory": "", "is_weighted": False}])}}]
            }
            from bodega.enrich import _categorize_batch
            _categorize_batch(["X"], base_url="https://openrouter.ai/api/v1", api_key="sk-or-test", model_id="deepseek/deepseek-v4-flash:nitro")
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer sk-or-test"


class TestProductsResource:
    def _run(self, new_descs, api_response):
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps(api_response)}}]
            }
            from bodega.enrich import products
            return list(products(new_descs, base_url="https://example.com/v1", api_key="test-key", model_id="test-model"))

    def test_yields_one_row_per_description(self):
        new_descs = [
            {"description_clean": "FILETE CABEZA LOMO", "supermarket": "MERCADONA"},
            {"description_clean": "PARAGUAYO",          "supermarket": "MERCADONA"},
        ]
        api_resp = [
            {"category": "MEAT_FISH",       "subcategory": "Pork",       "is_weighted": False},
            {"category": "FRUITS_VEGETABLES","subcategory": "Stone fruit","is_weighted": True},
        ]
        rows = self._run(new_descs, api_resp)
        assert len(rows) == 2

    def test_row_contains_all_required_fields(self):
        new_descs = [{"description_clean": "LECHE", "supermarket": "MERCADONA"}]
        api_resp  = [{"category": "DAIRY_EGGS", "subcategory": "Milk", "is_weighted": False}]
        row = self._run(new_descs, api_resp)[0]
        assert row["description_clean"] == "LECHE"
        assert row["supermarket"] == "MERCADONA"
        assert row["category"] == "DAIRY_EGGS"
        assert row["subcategory"] == "Milk"
        assert row["is_weighted"] is False
        assert "categorized_at" in row
        assert "llm_model" in row

    def test_subcategory_truncated_to_30_chars(self):
        long_sub = "A" * 50
        new_descs = [{"description_clean": "X", "supermarket": "MERCADONA"}]
        api_resp  = [{"category": "OTHER", "subcategory": long_sub, "is_weighted": False}]
        row = self._run(new_descs, api_resp)[0]
        assert len(row["subcategory"]) == 30

    def test_empty_input_yields_nothing(self):
        from bodega.enrich import products
        rows = list(products([], base_url="https://example.com/v1", api_key="k", model_id="m"))
        assert rows == []

    def test_batches_in_groups_of_30(self):
        new_descs = [{"description_clean": f"P{i}", "supermarket": "MERCADONA"} for i in range(65)]
        api_resp_30 = [{"category": "OTHER", "subcategory": "", "is_weighted": False}] * 30
        api_resp_05 = [{"category": "OTHER", "subcategory": "", "is_weighted": False}] * 5
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.side_effect = [
                {"choices": [{"message": {"content": json.dumps(api_resp_30)}}]},
                {"choices": [{"message": {"content": json.dumps(api_resp_30)}}]},
                {"choices": [{"message": {"content": json.dumps(api_resp_05)}}]},
            ]
            from bodega.enrich import products
            rows = list(products(new_descs, base_url="https://example.com/v1", api_key="k", model_id="m"))
        assert len(rows) == 65
        assert mock_post.call_count == 3


class TestFindNewDescriptionsLocal:
    def test_returns_empty_when_schema_missing(self, tmp_path):
        import duckdb
        db = tmp_path / "silver.duckdb"
        duckdb.connect(str(db)).close()

        from bodega.enrich import _find_new_descriptions_local
        assert _find_new_descriptions_local(str(db)) == []

    def test_returns_all_items_when_products_table_missing(self, tmp_path):
        import duckdb
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA bodega")
        con.execute(
            "CREATE TABLE bodega.invoice_items AS "
            "SELECT 'LECHE' AS description_clean, 'MERCADONA' AS supermarket"
        )
        con.close()

        from bodega.enrich import _find_new_descriptions_local
        result = _find_new_descriptions_local(str(db))
        assert len(result) == 1
        assert result[0]["description_clean"] == "LECHE"

    def test_excludes_already_categorised_descriptions(self, tmp_path):
        import duckdb
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA bodega")
        con.execute(
            "CREATE TABLE bodega.invoice_items AS "
            "SELECT * FROM (VALUES "
            "('LECHE', 'MERCADONA'), ('PAN', 'MERCADONA')) t(description_clean, supermarket)"
        )
        con.execute(
            "CREATE TABLE bodega.products AS "
            "SELECT 'LECHE' AS description_clean, 'MERCADONA' AS supermarket, "
            "'DAIRY_EGGS' AS subcategory"
        )
        con.close()

        from bodega.enrich import _find_new_descriptions_local
        result = _find_new_descriptions_local(str(db))
        assert len(result) == 1
        assert result[0]["description_clean"] == "PAN"

    def test_retries_parse_error_descriptions(self, tmp_path):
        import duckdb
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA bodega")
        con.execute(
            "CREATE TABLE bodega.invoice_items AS "
            "SELECT * FROM (VALUES "
            "('LECHE', 'MERCADONA'), ('PAN', 'MERCADONA')) t(description_clean, supermarket)"
        )
        con.execute(
            "CREATE TABLE bodega.products AS "
            "SELECT * FROM (VALUES "
            "('LECHE', 'MERCADONA', 'DAIRY_EGGS'), ('PAN', 'MERCADONA', 'PARSE_ERROR')) "
            "t(description_clean, supermarket, subcategory)"
        )
        con.close()

        from bodega.enrich import _find_new_descriptions_local
        result = _find_new_descriptions_local(str(db))
        assert len(result) == 1
        assert result[0]["description_clean"] == "PAN"

    def test_returns_empty_when_invoice_items_missing(self, tmp_path):
        import duckdb
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA bodega")
        con.close()

        from bodega.enrich import _find_new_descriptions_local
        assert _find_new_descriptions_local(str(db)) == []
