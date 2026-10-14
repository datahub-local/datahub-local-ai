################################
# Adjust path for local imports
###############################
import os
import sys

SCRIPT_DIR = os.path.realpath(os.path.dirname(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
print(f"Added {os.path.dirname(SCRIPT_DIR)} to sys.path")
###############################

from datetime import UTC, datetime, timedelta

from airflow import DAG
from airflow.sdk import task


def fetch_sample(context: dict | None = None) -> str:
    """Simulate fetching sample data. Returns a message for testing."""
    msg = "Fetching sample data..."
    print(msg)
    return msg


def process_sample(context: dict | None = None) -> str:
    """Simulate processing sample data. Returns a message for testing."""
    msg = "Processing sample data..."
    print(msg)
    return msg


default_args = {
    "owner": "datahub-local",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="example",
    default_args=default_args,
    description="Example ingestion DAG: raw -> bronze",
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    catchup=False,
) as dag:

    @task(task_id="fetch_sample")
    def _fetch():
        return fetch_sample({})

    @task(task_id="process_sample")
    def _process():
        return process_sample({})

    _fetch() >> _process()
