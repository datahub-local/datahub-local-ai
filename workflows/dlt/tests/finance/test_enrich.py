"""Unit tests for the finance LLM payee-categorisation pipeline.

No real Trino, DuckDB, or LiteLLM calls — ``call_llm`` is exercised through a
patched ``httpx.post`` exactly as bodega's enrich tests do.
"""

import json
from unittest.mock import patch


class TestCategorizeBatch:
    def _call(self, payees, api_response):
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps(api_response)}}]
            }
            from finance.enrich import _categorize_batch
            return _categorize_batch(payees, base_url="https://example.com/v1", api_key="test-key", model_id="test-model")

    def test_returns_one_result_per_payee(self):
        payees = ["MERCADONA", "RESTAURANTE EL SOL"]
        api_resp = [
            {"category": "GROCERIES", "subcategory": "Supermarket"},
            {"category": "DINING_OUT", "subcategory": "Restaurant"},
        ]
        results = self._call(payees, api_resp)
        assert len(results) == 2
        assert results[0]["category"] == "GROCERIES"
        assert results[1]["category"] == "DINING_OUT"

    def test_handles_wrapped_items_key(self):
        api_resp = {"items": [{"category": "TRANSPORT", "subcategory": "Metro"}]}
        results = self._call(["METRO MADRID"], api_resp)
        assert results[0]["category"] == "TRANSPORT"

    def test_falls_back_to_other_on_network_error(self):
        with patch("dlt_runner.llm.httpx.post", side_effect=Exception("network")):
            from finance.enrich import _categorize_batch
            results = _categorize_batch(["PAGO X"], base_url="https://example.com/v1", api_key="k", model_id="m")
        assert results[0]["category"] == "OTHER"
        assert results[0]["subcategory"] == "PARSE_ERROR"

    def test_falls_back_to_other_on_count_mismatch(self):
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps([{"category": "OTHER"}])}}]
            }
            from finance.enrich import _categorize_batch
            results = _categorize_batch(["PAYEE_A", "PAYEE_B"], base_url="https://example.com/v1", api_key="k", model_id="m")
        assert all(r["category"] == "OTHER" for r in results)

    def test_ollama_sends_no_auth_header(self):
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps([{"category": "OTHER", "subcategory": ""}])}}]
            }
            from finance.enrich import _categorize_batch
            _categorize_batch(["X"], base_url="http://datahub-local-core-data-ollama:11434/v1", api_key="", model_id="m")
        headers = mock_post.call_args.kwargs["headers"]
        assert "Authorization" not in headers

    def test_litellm_sends_bearer_token(self):
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps([{"category": "OTHER", "subcategory": ""}])}}]
            }
            from finance.enrich import _categorize_batch
            _categorize_batch(["X"], base_url="http://datahub-local-core-data-litellm:4000/v1", api_key="sk-litellm-test", model_id="opencode-go/deepseek-v4.1-flash")
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer sk-litellm-test"


class TestMerchantCategoriesResource:
    def _run(self, new_payees, api_response):
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps(api_response)}}]
            }
            from finance.enrich import merchant_categories
            return list(merchant_categories(new_payees, base_url="https://example.com/v1", api_key="test-key", model_id="test-model"))

    def test_yields_one_row_per_payee(self):
        new_payees = [
            {"payee_clean": "MERCADONA", "institution_id": "Openbank"},
            {"payee_clean": "RENFE",     "institution_id": "Openbank"},
        ]
        api_resp = [
            {"category": "GROCERIES", "subcategory": "Supermarket"},
            {"category": "TRAVEL",    "subcategory": "Train"},
        ]
        rows = self._run(new_payees, api_resp)
        assert len(rows) == 2

    def test_row_contains_all_required_fields(self):
        new_payees = [{"payee_clean": "IBERDROLA", "institution_id": "Openbank"}]
        api_resp = [{"category": "UTILITIES", "subcategory": "Electricity"}]
        row = self._run(new_payees, api_resp)[0]
        assert row["payee_clean"] == "IBERDROLA"
        assert row["category"] == "UTILITIES"
        assert row["subcategory"] == "Electricity"
        assert row["first_seen_institution"] == "Openbank"
        assert "categorized_at" in row
        assert "llm_model" in row

    def test_subcategory_truncated_to_30_chars(self):
        new_payees = [{"payee_clean": "X", "institution_id": "Openbank"}]
        api_resp = [{"category": "OTHER", "subcategory": "A" * 50}]
        row = self._run(new_payees, api_resp)[0]
        assert len(row["subcategory"]) == 30

    def test_empty_input_yields_nothing(self):
        from finance.enrich import merchant_categories
        rows = list(merchant_categories([], base_url="https://example.com/v1", api_key="k", model_id="m"))
        assert rows == []

    def test_batches_in_groups_of_30(self):
        new_payees = [{"payee_clean": f"P{i}", "institution_id": "Openbank"} for i in range(65)]
        api_resp_30 = [{"category": "OTHER", "subcategory": ""}] * 30
        api_resp_05 = [{"category": "OTHER", "subcategory": ""}] * 5
        with patch("dlt_runner.llm.httpx.post") as mock_post:
            mock_post.return_value.json.side_effect = [
                {"choices": [{"message": {"content": json.dumps(api_resp_30)}}]},
                {"choices": [{"message": {"content": json.dumps(api_resp_30)}}]},
                {"choices": [{"message": {"content": json.dumps(api_resp_05)}}]},
            ]
            from finance.enrich import merchant_categories
            rows = list(merchant_categories(new_payees, base_url="https://example.com/v1", api_key="k", model_id="m"))
        assert len(rows) == 65
        assert mock_post.call_count == 3


class TestFindNewPayeesLocal:
    def test_returns_empty_when_schema_missing(self, tmp_path):
        import duckdb
        db = tmp_path / "silver.duckdb"
        duckdb.connect(str(db)).close()

        from finance.enrich import _find_new_payees_local
        assert _find_new_payees_local(str(db)) == []

    def test_returns_all_payees_when_categories_table_missing(self, tmp_path):
        import duckdb
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA finance")
        con.execute(
            "CREATE TABLE finance.transactions AS "
            "SELECT 'MERCADONA' AS payee_clean, 'Openbank' AS institution_id"
        )
        con.close()

        from finance.enrich import _find_new_payees_local
        result = _find_new_payees_local(str(db))
        assert len(result) == 1
        assert result[0]["payee_clean"] == "MERCADONA"

    def test_excludes_already_categorised_payees(self, tmp_path):
        import duckdb
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA finance")
        con.execute(
            "CREATE TABLE finance.transactions AS "
            "SELECT * FROM (VALUES "
            "('MERCADONA', 'Openbank'), ('RENFE', 'Openbank')) t(payee_clean, institution_id)"
        )
        con.execute(
            "CREATE TABLE finance.merchant_categories AS "
            "SELECT 'MERCADONA' AS payee_clean, 'GROCERIES' AS subcategory"
        )
        con.close()

        from finance.enrich import _find_new_payees_local
        result = _find_new_payees_local(str(db))
        assert len(result) == 1
        assert result[0]["payee_clean"] == "RENFE"

    def test_retries_parse_error_payees(self, tmp_path):
        import duckdb
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA finance")
        con.execute(
            "CREATE TABLE finance.transactions AS "
            "SELECT * FROM (VALUES "
            "('MERCADONA', 'Openbank'), ('RENFE', 'Openbank')) t(payee_clean, institution_id)"
        )
        con.execute(
            "CREATE TABLE finance.merchant_categories AS "
            "SELECT * FROM (VALUES "
            "('MERCADONA', 'GROCERIES'), ('RENFE', 'PARSE_ERROR')) t(payee_clean, subcategory)"
        )
        con.close()

        from finance.enrich import _find_new_payees_local
        result = _find_new_payees_local(str(db))
        assert len(result) == 1
        assert result[0]["payee_clean"] == "RENFE"

    def test_keys_on_payee_clean_alone_across_institutions(self, tmp_path):
        import duckdb
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA finance")
        con.execute(
            "CREATE TABLE finance.transactions AS "
            "SELECT * FROM (VALUES "
            "('MERCADONA', 'Openbank'), ('MERCADONA', 'CaixaBank')) t(payee_clean, institution_id)"
        )
        con.close()

        from finance.enrich import _find_new_payees_local
        result = _find_new_payees_local(str(db))
        assert len(result) == 1
        assert result[0]["payee_clean"] == "MERCADONA"
        assert result[0]["institution_id"] == "CaixaBank"

    def test_returns_empty_when_transactions_missing(self, tmp_path):
        import duckdb
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA finance")
        con.close()

        from finance.enrich import _find_new_payees_local
        assert _find_new_payees_local(str(db)) == []
