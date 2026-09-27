"""Create the n8n DataTables this repo's n8n workflows depend on.

The Visual Studio workflow is generic and stateless between runs: parameters
arrive on the trigger (sub-workflow call, `POST /webhook/visual-studio`, or the
form), and each execution records what it produced in the `visual_studio_table`
DataTable -- one row per run, keyed by `RUN_ID` (the n8n execution id), so a
result can be fetched over HTTP later. A DataTable is instance state, backed up
with the instance database; it is a documented setup step, not a repo artifact.
This script is that step, idempotent by table name.

    export N8N_URL=http://datahub-local-core-automation-n8n.automation.svc.cluster.local
    export N8N_API_KEY=...        # mount security/n8n-root, do not read into a shell
    python setup_data_tables.py            # dry run: print what would be created
    python setup_data_tables.py --apply    # create the missing tables

No `id`-style system columns are declared: a DataTable adds its own `id`.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://datahub-local-core-automation-n8n.automation.svc.cluster.local"

VISUAL_STUDIO_COLUMNS = [
    "RUN_ID", "STATUS", "REQUEST", "RESULT", "ASSET_COUNT", "ERROR",
]

TABLES = {
    "visual_studio_table": [{"name": c, "type": "string"} for c in VISUAL_STUDIO_COLUMNS],
}


def api(url, key, path, method="GET", body=None):
    req = urllib.request.Request(
        url + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"X-N8N-API-KEY": key, "Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} failed: {e.code} {e.read().decode()[:400]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="create the missing tables")
    args = ap.parse_args()

    key = os.environ.get("N8N_API_KEY")
    if not key:
        sys.exit("N8N_API_KEY unset -- mount security/n8n-root into the pod")
    url = os.environ.get("N8N_URL", DEFAULT_URL).rstrip("/")

    existing = {t["name"] for t in api(url, key, "/api/v1/data-tables").get("data", [])}
    for name, columns in TABLES.items():
        if name in existing:
            print(f"{name}: exists -- left untouched")
            continue
        print(f"{name}: missing, {len(columns)} columns")
        if not args.apply:
            continue
        created = api(url, key, "/api/v1/data-tables", "POST",
                      {"name": name, "columns": columns})
        print(f"  created id={created.get('id')} columns={len(created.get('columns', []))}")
    if not args.apply:
        print("\ndry run -- rerun with --apply to create")


if __name__ == "__main__":
    main()
