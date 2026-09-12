import importlib


def _dag():
    return importlib.import_module("dags.bodega_dag").dag


def test_dag_importable():
    dag = _dag()
    assert dag.dag_id == "bodega_daily"
    assert set(dag.task_ids) == {
        "n8n_download_invoices",
        "dlt_ingest_bodega",
        "dbt_silver_bodega",
        "dlt_enrich_bodega",
        "dbt_gold_bodega",
    }


def test_dag_schedule():
    assert _dag().schedule == "0 8 * * *"


def test_task_ordering():
    dag = _dag()
    assert "dlt_ingest_bodega" in dag.get_task("n8n_download_invoices").downstream_task_ids
    assert "dbt_silver_bodega" in dag.get_task("dlt_ingest_bodega").downstream_task_ids
    assert "dlt_enrich_bodega" in dag.get_task("dbt_silver_bodega").downstream_task_ids
    assert "dbt_gold_bodega" in dag.get_task("dlt_enrich_bodega").downstream_task_ids


def test_n8n_download_invoices():
    mod = importlib.import_module("dags.bodega_dag")
    task = mod.dag.get_task("n8n_download_invoices")
    assert task.op_kwargs["workflow_name"] == mod.N8N_DOWNLOAD_INVOICES_WORKFLOW_NAME
    assert task.op_kwargs["workflow_name"] == "DownloadInvoicesFromGmail"
    assert task.op_kwargs["params"] == {
        "FROM_DATE": mod.FROM_DATE_EXPR,
        "TO_DATE": mod.TO_DATE_EXPR,
        "BATCH_TIMESTAMP": mod.BATCH_TIMESTAMP_EXPR,
    }


def test_dag_params_default_to_none():
    # Defaults must be static (no datetime.now()) so DAG parsing doesn't bump the DAG
    # version on every parse; the rolling window is computed via Jinja macros instead.
    # Types are nullable ["string", "null"] so the Trigger DAG UI doesn't treat them
    # as required and disable submit when left blank.
    dag = _dag()
    assert set(dag.params) == {"from_date", "to_date"}
    assert dag.params["from_date"] is None
    assert dag.params["to_date"] is None


def test_date_exprs_fall_back_to_macros():
    mod = importlib.import_module("dags.bodega_dag")
    assert "macros.ds_add(macros.datetime.now() | ds, -7)" in mod.FROM_DATE_EXPR
    assert "params.from_date or" in mod.FROM_DATE_EXPR
    assert "macros.datetime.now() | ds" in mod.TO_DATE_EXPR
    assert "params.to_date or" in mod.TO_DATE_EXPR


def test_dlt_ingest_arguments():
    ingest = _dag().get_task("dlt_ingest_bodega")
    assert ingest.arguments == [
        "--pipeline", "ingest", "--project", "bodega", "--target", "homelab",
    ]


def test_dlt_enrich_arguments():
    enrich = _dag().get_task("dlt_enrich_bodega")
    assert enrich.arguments == [
        "--pipeline", "enrich", "--project", "bodega", "--target", "homelab",
    ]


def test_dbt_silver_arguments():
    task = _dag().get_task("dbt_silver_bodega")
    assert task.arguments == [
        "--project", "bodega", "--target", "homelab", "--select", "silver.*",
    ]


def test_dbt_gold_arguments():
    task = _dag().get_task("dbt_gold_bodega")
    assert task.arguments == [
        "--project", "bodega", "--target", "homelab", "--select", "gold.*",
    ]


def test_ingest_kafka_env_vars():
    ingest = _dag().get_task("dlt_ingest_bodega")
    env_map = {e.name: e for e in ingest.env_vars}
    assert "KAFKA_BOOTSTRAP_SERVERS" in env_map
    assert "redpanda" in env_map["KAFKA_BOOTSTRAP_SERVERS"].value
    assert env_map["KAFKA_TOPIC_BODEGA"].value == "bodega_invoices"


def test_ingest_date_window_env_vars():
    mod = importlib.import_module("dags.bodega_dag")
    ingest = mod.dag.get_task("dlt_ingest_bodega")
    env_map = {e.name: e for e in ingest.env_vars}
    assert env_map["BODEGA_FROM_DATE"].value == mod.FROM_DATE_EXPR
    assert env_map["BODEGA_TO_DATE"].value == mod.TO_DATE_EXPR
    assert env_map["BODEGA_BATCH_TIMESTAMP"].value == mod.BATCH_TIMESTAMP_EXPR


def test_ingest_s3_secrets():
    ingest = _dag().get_task("dlt_ingest_bodega")
    env_map = {e.name: e for e in ingest.env_vars}
    assert env_map["S3_ACCESS_KEY"].value_from.secret_key_ref.name == "s3-credentials"
    assert env_map["S3_SECRET_KEY"].value_from.secret_key_ref.name == "s3-credentials"


def test_enrich_s3_secrets():
    enrich = _dag().get_task("dlt_enrich_bodega")
    env_map = {e.name: e for e in enrich.env_vars}
    assert env_map["S3_ACCESS_KEY"].value_from.secret_key_ref.name == "s3-credentials"
    assert env_map["S3_SECRET_KEY"].value_from.secret_key_ref.name == "s3-credentials"


def test_enrich_litellm_secret():
    enrich = _dag().get_task("dlt_enrich_bodega")
    env_map = {e.name: e for e in enrich.env_vars}
    secret_ref = env_map["LITELLM_API_KEY"].value_from.secret_key_ref
    assert secret_ref.name == "litellm-auth-credentials"
    assert secret_ref.key == "api_key"
