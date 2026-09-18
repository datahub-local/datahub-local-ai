# dlt Pipelines

[dlt](https://dlthub.com) ingest/export pipelines for `datahub-local-ai`. Handles the
data movement *around* dbt — loading source data into bronze and exporting dbt-built tables.

- **ingest** — loads the automotive CSV into `bronze.example_db.automotive_source`, which dbt reads as a source.
- **export** — reverse-ETLs the dbt-built silver/gold tables to Postgres (homelab) or a DuckDB file (local).

Only `example_db` has ingest/export; `pi` is pure dbt compute.

## Contents

```
workflows/dlt/
  dlt_runner/         entry point: python -m dlt_runner --pipeline <ingest|export> --project <name> --target <env>
    __main__.py       CLI argument parsing and pipeline dispatch
  example_db/         automotive dataset pipeline
    config.py         env-driven config (catalog→warehouse map, DuckDB paths, DSNs)
    ingest.py         CSV → bronze medallion layer
    export.py         silver/gold → Postgres or DuckDB export file
  finance/            personal banking pipeline (spec 005; Enable Banking provider)
    config.py         env-driven config (Enable Banking accounts, FINANCE_* windows)
    onboard.py        onboarding CLI (consent flow → accounts.json fragment)
    providers/        `BankDataProvider` protocol + EnableBanking adapter
  tests/
    example_db/       integration test (local DuckDB ingest + export end-to-end)
    finance/          adapter + onboarding unit tests (synthetic fixtures, mock transport)
    test_config.py    config unit tests
  Dockerfile
  pyproject.toml      package: datahub-local-ai-dlt
```

## Pipelines

| Pipeline     | Ingest source                      | Export destination            | Notes                            |
| ------------ | ---------------------------------- | ----------------------------- | -------------------------------- |
| `example_db` | Automotive CSV (URL or local file) | Postgres / DuckDB export file | Only pipeline with ingest+export |

## Targets

| Target              | Ingest destination                            | Export destination | Staging                |
| ------------------- | --------------------------------------------- | ------------------ | ---------------------- |
| `homelab` (default) | Iceberg via Apache Polaris REST + S3 (Garage) | Postgres           | Parquet in temp bucket |
| `local`             | `bronze.duckdb` (same file dbt reads)         | `export.duckdb`    | —                      |

The local DuckDB files are the **same files the dbt `local` target uses** (`DBT_DUCKDB_*`), so
`dlt ingest → dbt build → dlt export` works without any external services.

## How to use it

```bash
cd workflows/dlt
uv sync --extra dev

# Full local chain — no external infra needed
export DBT_DUCKDB_DIR=/tmp/duckdb
uv run python -m dlt_runner --pipeline ingest  --project example_db --target local
#   then: cd ../dbt && uv run python -m dbt_runner --project example_db --target local
uv run python -m dlt_runner --pipeline export  --project example_db --target local

# Homelab target — Polaris / S3 / Postgres required
uv run python -m dlt_runner --pipeline ingest  --project example_db --target homelab
uv run python -m dlt_runner --pipeline export  --project example_db --target homelab
```

## Tests

```bash
cd workflows/dlt
uv sync --extra dev

uv run pytest                           # config unit tests + local DuckDB integration
uv run pytest tests/example_db/ -v     # integration only
uv run ruff check .
```

## Docker

```bash
cd workflows/dlt
docker build -t datahub-local-ai-dlt .
docker run --rm -e DBT_DUCKDB_DIR=/data datahub-local-ai-dlt \
  --pipeline ingest --project example_db --target local
```

## Finance onboarding (Enable Banking)

The bank consent is a browser flow (PSD2 strong customer authentication) and is
the **only manual step** in the finance pipeline. It happens once per account per
consent window (~180 days); the daily DAG reuses the session the onboarding
produced and never consents on its own. Actual Budget's *built-in* bank sync
must stay unconfigured — it would become a second fetcher competing for the same
per-account daily budget (spec 005 §5, the recorded ordering mistake).

### First link / re-link

```bash
cd workflows/dlt
export ENABLEBANKING_PRIVATE_KEY_FILE=~/Downloads/<app-id>.pem  # key from app registration
export ENABLEBANKING_APP_ID=<app-id>                            # also the JWT kid
export ENABLEBANKING_REDIRECT_URL=<one whitelisted redirect URL>

uv run python -m finance.onboard aspsps                          # 1. exact bank name
uv run python -m finance.onboard auth --aspsp "<bank name>"      # 2. open URL, approve
uv run python -m finance.onboard session --code <code> --alias <alias>   # 3. paste block
```

The browser lands on the redirect URL carrying `?code=...`; the page itself does
not need to load. `session` prints an `accounts.json` fragment —
`{alias: {iban, uid, app_id, valid_until, institution_id}}` — to paste into the
`finance-enablebanking` secret (`datahub-local-secrets/release/values/default.yaml.gotmpl`,
rendered and applied from that repo).

### When a run fails with `ACCESS_EXPIRED`

1. Re-run the three commands above for the account the failure named.
2. Paste the fresh `uid` / `valid_until` into the secret **keeping the same
   alias**: the uid is session-scoped and changes every re-link, the alias is
   the pipeline identity — re-keying it would duplicate history in bronze.
3. If the failure is a 429 instead, nothing is expired: the account hit its
   per-endpoint daily budget. Re-run after the bank's reset; the fetch never
   retries in a loop.

## Actual Budget sync (`--pipeline sync`)

Pushes `silver.finance.transactions` into Actual Budget, deduped on
`imported_id = enablebanking:<stable_id>`. The `finance-actual` secret in
`datahub-local-secrets` carries `base_url`, `password`, `file` and
`accounts.json` (bank alias -> Actual account name).

Operator setup, once, before the first sync:

1. Log into Actual and set the server password to the value in
   `finance-actual.password` (Actual has no env for it — the UI stores a hash).
2. Map each Enable Banking alias to an Actual account name in
   `finance-actual.accounts.json`. An unmapped alias fails the run naming it.
   The account is created on the first sync if it does not exist
   (`get_or_create_account`, matched by name); actualpy sets only the name and
   `offbudget`, so create it by hand first if it needs a specific type. Names
   must stay stable — a UI rename makes the next sync create a new account.
3. Name the budget exactly as `finance-actual.file` (`Finance`). Actual mints
   the Sync ID and offers no way to choose it, so `file` is pinned to the
   budget **name**, which `actualpy` matches alongside the file id and the sync
   id. Rename the budget only together with that secret key.

`local` is dry-run by default; `FINANCE_SYNC_DRY_RUN=true` makes a homelab run
log what it would add without committing. A 60-day window re-reads silver, so
late-posted corrections are picked up and the `imported_id` check keeps
re-runs idempotent.

Actual never runs the budget's rules over transactions inserted through
actualpy, so the sync calls `run_rules()` itself: on the new rows, and on any
existing transaction still lacking a category (a backfill that never overwrites
a category a human set). Categorisation is still the budget's — the pipeline
only triggers the rules, it never picks a category itself.

Those rules are seeded from the lake, not invented: every merchant in
`silver.finance.merchant_categories` becomes a category under the
`Auto-categorised` group and one `payee -> category` rule, and a catch-all
`amount_inflow > 0 -> Income` rule makes credits count as income. Generated
rules are upserted by deterministic id (`uuid5` of the merchant key) and run in
the `pre` stage, so a re-run never duplicates them and any rule you write in the
Actual UI overrides them. The payee is the clean merchant key (`payee_clean`);
the raw bank text is kept as `imported_payee`. The lake's `INCOME` category maps
onto Actual's own `Income` category.

## Environment variables

| Variable                                                     | Default                                                   | Used by          |
| ------------------------------------------------------------ | --------------------------------------------------------- | ---------------- |
| `EXAMPLE_DB_SOURCE_URL`                                      | automotive CSV on GitHub                                  | ingest           |
| `DLT_TEMP_BUCKET`                                            | `datahub-local-temp`                                      | ingest (homelab) |
| `ICEBERG_CATALOG_URI`                                        | `http://datahub-local-core-data-polaris:8181/api/catalog` | ingest (homelab) |
| `S3_ENDPOINT` / `S3_ACCESS_KEY` / `S3_SECRET_KEY`            | Garage endpoint / —                                       | ingest (homelab) |
| `TRINO_HOST` / `TRINO_PORT` / `TRINO_USER`                   | `datahub-local-core-data-trino` / `8080` / `dbt`          | export (homelab) |
| `EXAMPLE_DB_URL` / `EXAMPLE_DB_USER` / `EXAMPLE_DB_PASSWORD` | —                                                         | export (homelab) |
| `EXAMPLE_DB_SCHEMA`                                          | `public`                                                  | export           |
| `DBT_DUCKDB_DIR` / `DBT_DUCKDB_*`                            | `/tmp/duckdb`                                             | local            |
| `DLT_EXPORT_DUCKDB_PATH`                                     | `<dir>/export.duckdb`                                     | export (local)   |
| `ENABLEBANKING_PRIVATE_KEY` / `ENABLEBANKING_PRIVATE_KEY_FILE` | — (PEM from app registration)                           | finance          |
| `ENABLEBANKING_APP_ID`                                       | — (application id, the JWT `kid`)                         | finance          |
| `ENABLEBANKING_ACCOUNTS`                                     | — (the secret's `accounts.json` JSON)                     | finance          |
| `ENABLEBANKING_BASE_URL`                                     | `https://api.enablebanking.com`                           | finance          |
| `ENABLEBANKING_REDIRECT_URL`                                 | — (must be whitelisted on the application)                | onboard          |
| `FINANCE_FETCH_STRATEGY`                                     | `default` (`longest` on backfill runs)                    | finance          |
| `FINANCE_FROM_DATE` / `FINANCE_TO_DATE`                      | — (14-day DAG lookback)                                   | finance          |
| `FINANCE_PAYEE_LANGUAGE`                                     | `Spanish`                                                 | finance (enrich) |
| `FINANCE_SYNC_WINDOW_DAYS`                                   | `60`                                                      | finance (sync)   |
| `FINANCE_SYNC_FROM_DATE` / `FINANCE_SYNC_TO_DATE`            | — (full-history first run / today)                        | finance (sync)   |
| `FINANCE_SYNC_DRY_RUN`                                       | `false` (`local` target is dry-run regardless)            | finance (sync)   |
| `FINANCE_ACTUAL_BASE_URL` / `FINANCE_ACTUAL_PASSWORD` / `FINANCE_ACTUAL_FILE` | — (finance-actual secret)            | finance (sync)   |
| `FINANCE_ACTUAL_ACCOUNTS`                                    | — (`{"<alias>": "<Actual account>"}` JSON)                | finance (sync)   |
