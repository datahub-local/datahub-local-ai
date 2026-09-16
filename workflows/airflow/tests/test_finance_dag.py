from __future__ import annotations

import importlib

from utils import DEFAULT_TARGET


def _module():
    return importlib.import_module("dags.finance_dag")


def _dag():
    return _module().dag


def test_dag_importable():
    dag = _dag()
    assert dag.dag_id == "finance_daily"
    # the sync task attaches next to dbt_gold once the Actual Budget server lands (WF-8/9)
    assert set(dag.task_ids) == {
        "dlt_ingest_finance",
        "dbt_silver_finance",
        "dlt_enrich_finance",
        "dbt_gold_finance",
    }


def test_dag_schedule():
    assert _dag().schedule == "0 6 * * *"


def test_dag_params_default_to_none():
    dag = _dag()
    assert set(dag.params) == {"from_date", "to_date"}
    assert dag.params["from_date"] is None
    assert dag.params["to_date"] is None


def test_ingest_date_window_env_vars():
    mod = _module()
    ingest = mod.dag.get_task("dlt_ingest_finance")
    env_map = {e.name: e for e in ingest.env_vars}
    assert env_map["FINANCE_FROM_DATE"].value == mod.FROM_DATE_EXPR
    assert env_map["FINANCE_TO_DATE"].value == mod.TO_DATE_EXPR


def test_ingest_wires_both_enablebanking_secrets():
    mod = _module()
    ingest = mod.dag.get_task("dlt_ingest_finance")
    env_map = {e.name: e for e in ingest.env_vars}
    assert env_map["ENABLEBANKING_PRIVATE_KEY"].value_from.secret_key_ref.name == "finance-enablebanking"
    assert env_map["ENABLEBANKING_PRIVATE_KEY"].value_from.secret_key_ref.key == "private_key"
    assert env_map["ENABLEBANKING_ACCOUNTS"].value_from.secret_key_ref.key == "accounts.json"
    assert env_map["ENABLEBANKING_TOKENS"].value_from.secret_key_ref.name == "finance-enablebanking-token"
    assert env_map["ENABLEBANKING_TOKENS"].value_from.secret_key_ref.key == "tokens.json"
    assert not hasattr(ingest, "op_kwargs") or "workflow_name" not in getattr(ingest, "op_kwargs", {})


def test_ingest_s3_and_polaris_secrets():
    mod = _module()
    ingest = mod.dag.get_task("dlt_ingest_finance")
    env_map = {e.name: e for e in ingest.env_vars}
    assert env_map["S3_ACCESS_KEY"].value_from.secret_key_ref.name == "s3-credentials"
    assert env_map["S3_SECRET_KEY"].value_from.secret_key_ref.name == "s3-credentials"
    assert env_map["POLARIS_CLIENT_ID"].value_from.secret_key_ref.name == "polaris-auth-credentials"
    assert env_map["POLARIS_CLIENT_SECRET"].value_from.secret_key_ref.key == "password"


def test_14_day_lookback_window():
    mod = _module()
    assert "-14" in mod.FROM_DATE_EXPR
    assert "params.from_date or" in mod.FROM_DATE_EXPR
    assert "macros.datetime.now() | ds" in mod.TO_DATE_EXPR
    assert "params.to_date or" in mod.TO_DATE_EXPR


def test_dbt_tasks_select_each_layer():
    mod = _module()
    silver = mod.dag.get_task("dbt_silver_finance")
    gold = mod.dag.get_task("dbt_gold_finance")
    assert silver.arguments == ["--project", "finance", "--target", DEFAULT_TARGET, "--select", "silver.*"]
    assert gold.arguments == ["--project", "finance", "--target", DEFAULT_TARGET, "--select", "gold.*"]


def test_enrich_wires_iceberg_and_litellm_secrets():
    mod = _module()
    enrich = mod.dag.get_task("dlt_enrich_finance")
    env_map = {e.name: e for e in enrich.env_vars}
    assert env_map["S3_ACCESS_KEY"].value_from.secret_key_ref.name == "s3-credentials"
    assert env_map["POLARIS_CLIENT_ID"].value_from.secret_key_ref.name == "polaris-auth-credentials"
    assert env_map["LITELLM_API_KEY"].value_from.secret_key_ref.name == "litellm-auth-credentials"
    assert env_map["LITELLM_API_KEY"].value_from.secret_key_ref.key == "api_key"


def test_task_chain_order():
    mod = _module()
    dag = mod.dag
    order = ["dlt_ingest_finance", "dbt_silver_finance", "dlt_enrich_finance", "dbt_gold_finance"]
    for upstream, downstream in zip(order, order[1:]):
        assert downstream in {
            d.task_id for d in dag.get_task(upstream).downstream_list
        }, f"{upstream} -> {downstream}"
