# Bodega — Shopping Analytics Project Spec

> **Name rationale**: *Bodega* is Spanish slang for the neighbourhood store you know inside-out — fitting for a Mercadona analytics pipeline. It also evokes the NYC bodega: the local shop whose shelves you could map from memory. The goal of this project is exactly that.

---

## 1. Naming & Propagation

| Artifact                   | Name                    |
| -------------------------- | ----------------------- |
| Project                    | `bodega`                |
| Kafka topic                | `bodega_invoices`       |
| Bronze catalog / schema    | `bronze.bodega`         |
| Silver catalog / schema    | `silver.bodega`         |
| Gold catalog / schema      | `gold.bodega`           |
| Airflow DAG                | `bodega_daily`          |
| dlt ingest pipeline path   | `workflows/dlt/bodega/` |
| dbt transform project path | `workflows/dbt/bodega/` |
| Superset dashboard         | `Bodega`                |

### n8n propagation

The `Kafka` node in `download_invoices_from_gmail` currently has no topic set. Add `"topic": "bodega_invoices"` to its parameters. The message value should be the full parsed invoice JSON output of `parse_mercadona_invoice`.

**Also verify**: confirm whether Kafka receives the raw message from `set_output` before parsing, or the parsed JSON after `parse_mercadona_invoice`. The Bronze table's flatten function must match whichever schema lands in the topic.

### Iceberg / Polaris catalogs

Three medallion catalogs following the same pattern as `example_db`. Table names:

```
bronze.bodega.raw_invoices
silver.bodega.invoices
silver.bodega.invoice_items
silver.bodega.invoice_taxes
silver.bodega.stores
silver.bodega.products
gold.bodega.spending_by_day
gold.bodega.spending_by_week
gold.bodega.top_products
gold.bodega.price_trends
gold.bodega.category_spending
gold.bodega.tax_summary
```

Catalogs `bronze`, `silver`, `gold` are provisioned in Apache Polaris and exposed via Trino. No new catalog creation is required — only the `bodega` schema is new within each.

---

## 2. Infrastructure Addresses

| Service                   | Internal DNS                                                                                 | Port   | Notes                       |
| ------------------------- | -------------------------------------------------------------------------------------------- | ------ | --------------------------- |
| Redpanda (Kafka) broker-0 | `datahub-local-core-data-redpanda-0.datahub-local-core-data-redpanda.data.svc.cluster.local` | `9093` | no auth, no TLS             |
| Redpanda (Kafka) broker-1 | `datahub-local-core-data-redpanda-1.datahub-local-core-data-redpanda.data.svc.cluster.local` | `9093` |                             |
| Redpanda (Kafka) broker-2 | `datahub-local-core-data-redpanda-2.datahub-local-core-data-redpanda.data.svc.cluster.local` | `9093` |                             |
| Trino                     | `datahub-local-core-data-trino-trino.data.svc.cluster.local`                                 | `8080` | query engine for all layers |
| Superset                  | `datahub-local-core-data-superset.data.svc.cluster.local`                                    | `8088` |                             |

**`KAFKA_BOOTSTRAP_SERVERS`** (all three brokers for reliability):
```
datahub-local-core-data-redpanda-0.datahub-local-core-data-redpanda.data.svc.cluster.local:9093,datahub-local-core-data-redpanda-1.datahub-local-core-data-redpanda.data.svc.cluster.local:9093,datahub-local-core-data-redpanda-2.datahub-local-core-data-redpanda.data.svc.cluster.local:9093
```

**Topic `bodega_invoices` does not yet exist.** Create it before the first n8n run:
```bash
kubectl exec -n data datahub-local-core-data-redpanda-0 -c redpanda -- \
  rpk topic create bodega_invoices --partitions 3 --replicas 3
```

---

## 3. Source Schema

Formal JSON Schema: [agents/n8n/schemas/bodega_invoice.schema.json](../agents/n8n/schemas/bodega_invoice.schema.json)

The `parse_mercadona_invoice` n8n node produces one JSON object per invoice. Each object becomes **one Kafka message value** on topic `bodega_invoices`. Flow: `parse_mercadona_invoice` → `loop_messages` → `set_output` (passthrough, `includeOtherFields: true`) → `Kafka`.

```json
{
  "store": {
    "name":    "MERCADONA, S.A.",
    "vat_id":  "A-46103834",
    "address": "C/ LOLO RICO 1, 28523 RIVAS-VACIAMADRID",
    "phone":   "917578853"
  },
  "invoice": {
    "number":   "4693-010-579596",
    "operator": "3436290",
    "date":     "2025-07-16T09:31:00"
  },
  "items": [
    { "description": "FILETE CABEZA LOMO", "quantity": 1,     "unit_price": 3.60, "total": 3.60 },
    { "description": "PARAGUAYO",          "quantity": 0.886, "unit_price": 3.30, "total": 2.92 },
    { "description": "POMADA PAÑAL",       "quantity": 2,     "unit_price": 2.75, "total": 5.50 }
  ],
  "totals": {
    "amount": 24.45,
    "payment_method": "TARJETA BANCARIA",
    "card_type":      "DEBIT MASTERCARD",
    "card_number":    "**** **** **** 6403"
  },
  "taxes": [
    { "rate": "4%",  "base": 8.38, "tax": 0.34 },
    { "rate": "10%", "base": 8.16, "tax": 0.82 },
    { "rate": "21%", "base": 5.58, "tax": 1.17 }
  ]
}
```

### Field notes (from reading the JS parser)

| Field                 | Type     | Notes                                                                      |
| --------------------- | -------- | -------------------------------------------------------------------------- |
| `invoice.date`        | `string` | Format `YYYY-MM-DDTHH:MM:00` — seconds hard-coded to `00`, **no timezone** |
| `items[*].quantity`   | `number` | Integer for packaged; float (kg) for weighted items                        |
| `items[*].unit_price` | `number` | EUR per unit **or** EUR/kg for weighted                                    |
| `totals.card_number`  | `string` | Always masked as `**** **** **** NNNN`                                     |
| `taxes[*].rate`       | `string` | Pattern `^\d+%$` — not an enum, rates can change by law                    |
| `invoice.number`      | `string` | Natural dedup key. Pattern: `DDDD-DDD-DDDDDD`                              |

### Three item line variants

The parser handles three distinct receipt formats:
1. **Packaged single** — `1 PRODUCT_NAME PRICE` → `quantity=1, unit_price=PRICE, total=PRICE`
2. **Packaged multi** — `N PRODUCT_NAME UNIT_PRICE TOTAL` → `quantity=N, unit_price, total`
3. **Weighted by kg** — two lines: `PRODUCT_NAME` then `0.NNN kg PRICE €/kg TOTAL` → `quantity=float`

---

## 4. Architecture

```
n8n (DownloadInvoicesFromGmail)
  └─► Kafka topic: bodega_invoices
         │
         ▼  (dlt pipeline — Kafka source)
  bronze.bodega.raw_invoices   [Iceberg / Polaris]
         │
         ├─► silver.bodega.invoices         (SQL)
         ├─► silver.bodega.invoice_items    (SQL — UNNEST items_json)
         ├─► silver.bodega.invoice_taxes    (SQL — UNNEST taxes_json)
         ├─► silver.bodega.stores           (SQL — SCD1 dimension)
         └─► silver.bodega.products         (Python — LLM enrichment via dlt)
                      │
                      ▼ (all silver feeds gold)
         ├─► gold.bodega.spending_by_day
         ├─► gold.bodega.spending_by_week
         ├─► gold.bodega.top_products
         ├─► gold.bodega.price_trends
         ├─► gold.bodega.category_spending
         └─► gold.bodega.tax_summary
                      │
                      ▼
              Apache Superset (Bodega dashboard)
```

### Orchestration

Airflow DAG `bodega_daily`, schedule `0 8 * * *` (08:00 UTC). Four tasks in sequence:

```
bodega_daily
├── dlt_ingest_bodega            (dlt: Kafka → bronze.bodega.raw_invoices)
├── dbt_silver_bodega            (SQL: bronze → silver.{invoices, invoice_items, invoice_taxes, stores})
├── dlt_enrich_bodega_products   (dlt/Python: LLM → silver.bodega.products)
└── dbt_gold_bodega              (SQL: silver → gold.bodega.*)
```

`products` must be populated before gold runs, which is why the enrichment step sits between the two dbt tasks.

---

## 5. Bronze Layer

### Design decisions

**dlt Kafka drain (no Spark Structured Streaming)**

A dlt resource that acts as a micro-batch Kafka consumer: poll until N consecutive empty polls, then return. At ≤365 messages/year, raw throughput is not a concern. dlt handles the Iceberg write and deduplication.

**Consumer group offsets for state**

Consumer group `bodega-dlt-bronze` is stable across runs. The first run uses `auto.offset.reset=earliest` to backfill 1 year. Subsequent runs pick up from the last committed offset.

**Commit-then-insert risk**: Kafka offsets are committed as messages are polled. If dlt writes the batch but the Iceberg commit fails, the next run will not re-read those Kafka messages. Mitigation: the `merge` write disposition on `invoice_number` catches any gaps — if a row wasn't committed, reprocess from n8n. At ≤daily frequency this is acceptable.

**Raw JSON arrays kept as strings in Bronze**: `items_json` and `taxes_json` store the arrays as JSON strings. Explosion into rows happens in Silver, keeping Bronze as a faithful landing zone.

**Deduplication**: `write_disposition="merge"` on `invoice_number`. Even if n8n re-sends an invoice (e.g. after a re-run), Bronze absorbs it without duplication.

### Table: `bronze.bodega.raw_invoices`

| Column               | Type        | Notes                                               |
| -------------------- | ----------- | --------------------------------------------------- |
| `invoice_number`     | `VARCHAR`   | Primary key / dedup key                             |
| `invoice_date`       | `VARCHAR`   | Raw string `YYYY-MM-DDTHH:MM:00` — parsed in Silver |
| `operator_id`        | `VARCHAR`   |                                                     |
| `store_name`         | `VARCHAR`   | Raw, uppercased in Silver                           |
| `store_vat_id`       | `VARCHAR`   |                                                     |
| `store_address`      | `VARCHAR`   |                                                     |
| `store_phone`        | `VARCHAR`   |                                                     |
| `total_amount`       | `DOUBLE`    | EUR                                                 |
| `payment_method`     | `VARCHAR`   |                                                     |
| `card_type`          | `VARCHAR`   |                                                     |
| `card_number_masked` | `VARCHAR`   |                                                     |
| `items_json`         | `VARCHAR`   | JSON array string                                   |
| `taxes_json`         | `VARCHAR`   | JSON array string                                   |
| `supermarket`        | `VARCHAR`   | Hardcoded `MERCADONA`                               |
| `_kafka_offset`      | `BIGINT`    |                                                     |
| `_ingested_at`       | `TIMESTAMP` |                                                     |

### dlt ingest pipeline

File: `workflows/dlt/bodega/ingest.py`

```python
import json
import dlt
from confluent_kafka import Consumer, KafkaError


@dlt.resource(
    name="raw_invoices",
    write_disposition="merge",
    primary_key=["invoice_number"],
)
def raw_invoices(bootstrap_servers: str, topic: str, group_id: str = "bodega-dlt-bronze"):
    config = {
        "bootstrap.servers": bootstrap_servers,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "session.timeout.ms": 30000,
    }
    consumer = Consumer(config)
    consumer.subscribe([topic])

    idle_rounds, max_idle, poll_timeout = 0, 3, 10.0
    try:
        while idle_rounds < max_idle:
            msg = consumer.poll(timeout=poll_timeout)
            if msg is None:
                idle_rounds += 1
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    break
                raise RuntimeError(f"Kafka error: {msg.error()}")
            idle_rounds = 0
            data = json.loads(msg.value().decode("utf-8"))
            yield {
                "invoice_number":     data["invoice"]["number"],
                "invoice_date":       data["invoice"]["date"],
                "operator_id":        data["invoice"]["operator"],
                "store_name":         data["store"]["name"],
                "store_vat_id":       data["store"]["vat_id"],
                "store_address":      data["store"]["address"],
                "store_phone":        data["store"]["phone"],
                "total_amount":       float(data["totals"]["amount"]),
                "payment_method":     data["totals"]["payment_method"],
                "card_type":          data["totals"]["card_type"],
                "card_number_masked": data["totals"]["card_number"],
                "items_json":         json.dumps(data["items"]),
                "taxes_json":         json.dumps(data["taxes"]),
                "supermarket":        "MERCADONA",
                "_kafka_offset":      msg.offset(),
            }
            consumer.commit(message=msg, asynchronous=False)
    finally:
        consumer.close()
```

**Required dependency**: `confluent-kafka>=2.5` in `workflows/dlt/pyproject.toml`.

---

## 6. Silver Layer

### Design decisions

**Explosion in Silver, not Bronze**: `items_json` and `taxes_json` are raw strings in Bronze. Silver uses `CROSS JOIN UNNEST` (Trino) to create properly typed rows. This preserves Bronze as a landing zone and makes re-processing easy if the schema changes.

**`invoice_items` row identity**: The natural key is `(invoice_number, item_position)`. Items don't have their own identifiers in the Mercadona invoice; the ordinal position within the array is used, which is stable as long as n8n's parser is deterministic (it is).

**Product descriptions are noisy**: Mercadona abbreviates descriptions ("Q. LONCHAS CREMOSO", "200 SERVIL. BLANCAS"). Silver normalises them (`UPPER + TRIM`); the LLM enrichment in `silver.bodega.products` adds human-readable category.

**Stores SCD Type 1**: Mercadona stores rarely change. A full-refresh dimension is enough.

**No surrogate keys at Silver**: Natural keys (`invoice_number`, `store_vat_id`, `description_clean`) are stable enough.

---

### Table: `silver.bodega.invoices`

Cleaned invoice headers. One row per invoice.

- **Strategy**: incremental, merge on `invoice_number`
- **Grain**: `invoice_number`

```sql
SELECT
    invoice_number,
    date_parse(invoice_date, '%Y-%m-%dT%H:%i:%s')                      AS invoice_datetime,
    CAST(date_parse(invoice_date, '%Y-%m-%dT%H:%i:%s') AS DATE)        AS invoice_date,
    year(date_parse(invoice_date, '%Y-%m-%dT%H:%i:%s'))                AS invoice_year,
    month(date_parse(invoice_date, '%Y-%m-%dT%H:%i:%s'))               AS invoice_month,
    week(date_parse(invoice_date, '%Y-%m-%dT%H:%i:%s'))                AS invoice_week,
    operator_id,
    store_vat_id,
    trim(upper(store_name))                                             AS store_name,
    total_amount,
    (
        SELECT SUM(CAST(json_extract_scalar(t, '$.tax') AS DOUBLE))
        FROM UNNEST(CAST(json_parse(taxes_json) AS ARRAY(JSON))) AS t(t)
    )                                                                   AS total_tax_amount,
    (
        SELECT SUM(CAST(json_extract_scalar(t, '$.base') AS DOUBLE))
        FROM UNNEST(CAST(json_parse(taxes_json) AS ARRAY(JSON))) AS t(t)
    )                                                                   AS total_base_amount,
    payment_method,
    card_type,
    card_number_masked,
    supermarket,
    CARDINALITY(CAST(json_parse(items_json) AS ARRAY(JSON)))           AS item_count,
    _ingested_at
FROM bronze.bodega.raw_invoices
```

---

### Table: `silver.bodega.invoice_items`

Exploded line items. One row per product per invoice.

**Key decision**: weighted items have `quantity < 1` (decimal kg). A `unit` column (`EA` vs `KG`) derived from whether quantity is fractional distinguishes them for aggregation.

- **Strategy**: incremental, merge on `(invoice_number, item_position)`
- **Grain**: `(invoice_number, item_position)`

```sql
SELECT
    b.invoice_number,
    CAST(t.item_position AS INTEGER)                                              AS item_position,
    CAST(date_parse(b.invoice_date, '%Y-%m-%dT%H:%i:%s') AS DATE)                AS invoice_date,
    b.store_vat_id,
    b.supermarket,
    json_extract_scalar(t.item, '$.description')                                  AS description_raw,
    trim(upper(json_extract_scalar(t.item, '$.description')))                     AS description_clean,
    CAST(json_extract_scalar(t.item, '$.quantity')   AS DOUBLE)                   AS quantity,
    CASE
        WHEN CAST(json_extract_scalar(t.item, '$.quantity') AS DOUBLE)
             != FLOOR(CAST(json_extract_scalar(t.item, '$.quantity') AS DOUBLE))
        THEN 'KG' ELSE 'EA'
    END                                                                            AS unit,
    CAST(json_extract_scalar(t.item, '$.unit_price') AS DOUBLE)                   AS unit_price,
    CAST(json_extract_scalar(t.item, '$.total')      AS DOUBLE)                   AS total_amount
FROM bronze.bodega.raw_invoices AS b
CROSS JOIN UNNEST(CAST(json_parse(b.items_json) AS ARRAY(JSON)))
    WITH ORDINALITY AS t(item, item_position)
```

---

### Table: `silver.bodega.invoice_taxes`

Exploded tax breakdown. One row per tax rate per invoice.

- **Strategy**: incremental, merge on `(invoice_number, tax_rate)`

```sql
SELECT
    b.invoice_number,
    b.supermarket,
    CAST(date_parse(b.invoice_date, '%Y-%m-%dT%H:%i:%s') AS DATE)     AS invoice_date,
    json_extract_scalar(t.tax_entry, '$.rate')                          AS tax_rate,
    CAST(json_extract_scalar(t.tax_entry, '$.base') AS DOUBLE)          AS base_amount,
    CAST(json_extract_scalar(t.tax_entry, '$.tax')  AS DOUBLE)          AS tax_amount
FROM bronze.bodega.raw_invoices AS b
LEFT JOIN UNNEST(CAST(json_parse(b.taxes_json) AS ARRAY(JSON))) AS t(tax_entry) ON true
```

---

### Table: `silver.bodega.stores`

SCD Type 1 store dimension. Full refresh — there are at most a handful of distinct stores.

- **Strategy**: full refresh

```sql
SELECT
    store_vat_id                                                                    AS store_id,
    trim(upper(store_name))                                                         AS name,
    store_vat_id                                                                    AS vat_id,
    store_address                                                                   AS address,
    store_phone                                                                     AS phone,
    supermarket,
    MIN(CAST(date_parse(invoice_date, '%Y-%m-%dT%H:%i:%s') AS DATE))               AS first_seen_date,
    MAX(CAST(date_parse(invoice_date, '%Y-%m-%dT%H:%i:%s') AS DATE))               AS last_seen_date
FROM bronze.bodega.raw_invoices
GROUP BY store_vat_id, store_name, store_address, store_phone, supermarket
```

---

### Table: `silver.bodega.products` (LLM enrichment)

**The most interesting model.** A persistent lookup table that maps every distinct `description_clean` to a category. Incremental: only unseen descriptions trigger API calls. Already-categorised products are never re-queried.

#### Design decisions

**Batch API calls, not one-per-product**: A single OpenRouter call with up to 30 descriptions is far cheaper and faster than one call per product. The prompt returns a JSON array.

**Category taxonomy** (fixed set, returned by LLM):

| Code                   | Label                      |
| ---------------------- | -------------------------- |
| `FRUITS_VEGETABLES`    | Fruits & Vegetables        |
| `MEAT_FISH`            | Meat, Poultry & Fish       |
| `DAIRY_EGGS`           | Dairy, Eggs & Alternatives |
| `BAKERY_PASTRY`        | Bakery & Pastry            |
| `BEVERAGES`            | Beverages                  |
| `SNACKS_CONFECTIONERY` | Snacks & Confectionery     |
| `CLEANING_HOUSEHOLD`   | Cleaning & Household       |
| `PERSONAL_CARE`        | Personal Care & Health     |
| `BABY_PRODUCTS`        | Baby Products              |
| `FROZEN_FOODS`         | Frozen Foods               |
| `CANNED_PRESERVED`     | Canned & Preserved         |
| `PASTA_GRAINS`         | Pasta, Rice & Grains       |
| `CONDIMENTS_SAUCES`    | Condiments, Sauces & Oils  |
| `READY_MEALS`          | Ready Meals & Convenience  |
| `OTHER`                | Other / Unclassifiable     |

**Subcategory**: free-text, max 30 chars. The LLM picks a more specific label within the category (e.g. "Pork" under `MEAT_FISH`, "Citrus" under `FRUITS_VEGETABLES`).

**Model**: `xiaomi/mimo-v2.5:nitro` via OpenRouter (confirmed). Parameterised via `OPENROUTER_MODEL` env var — change it without touching pipeline code.

**Failure handling**: if the LLM call fails or returns an unparseable response, fall back to `OTHER` with subcategory `PARSE_ERROR`. Never block the pipeline.

#### Schema

| Column              | Type        |
| ------------------- | ----------- |
| `description_clean` | `VARCHAR`   |
| `supermarket`       | `VARCHAR`   |
| `category`          | `VARCHAR`   |
| `subcategory`       | `VARCHAR`   |
| `is_weighted`       | `BOOLEAN`   |
| `categorized_at`    | `TIMESTAMP` |
| `llm_model`         | `VARCHAR`   |

- **Strategy**: incremental, merge on `(description_clean, supermarket)`

#### dlt enrichment pipeline

File: `workflows/dlt/bodega/enrich.py`

```python
import httpx
import json
import dlt
from sqlalchemy import create_engine, text


SYSTEM_PROMPT = """You are an expert at categorising Spanish supermarket products.
Given a list of Mercadona product descriptions (abbreviated Spanish text), classify each one.

Allowed categories: FRUITS_VEGETABLES, MEAT_FISH, DAIRY_EGGS, BAKERY_PASTRY, BEVERAGES,
SNACKS_CONFECTIONERY, CLEANING_HOUSEHOLD, PERSONAL_CARE, BABY_PRODUCTS, FROZEN_FOODS,
CANNED_PRESERVED, PASTA_GRAINS, CONDIMENTS_SAUCES, READY_MEALS, OTHER.

Return ONLY a JSON array, one object per description, in the same order, with fields:
  category (one of the allowed values), subcategory (specific label, max 30 chars),
  is_weighted (true if typically sold by kg/weight, else false).
No explanation, no markdown, just the JSON array."""


def _categorize_batch(descriptions: list, api_key: str, model_id: str) -> list:
    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_id,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": json.dumps(descriptions)},
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        items = parsed if isinstance(parsed, list) else parsed.get("items", parsed.get("results", []))
        if len(items) == len(descriptions):
            return items
    except Exception:
        pass
    return [{"category": "OTHER", "subcategory": "PARSE_ERROR", "is_weighted": False}] * len(descriptions)


@dlt.resource(
    name="products",
    write_disposition="merge",
    primary_key=["description_clean", "supermarket"],
)
def products(trino_dsn: str, api_key: str, model_id: str = "xiaomi/mimo-v2.5:nitro"):
    from datetime import datetime, timezone

    engine = create_engine(trino_dsn)
    with engine.connect() as conn:
        existing = {
            (r.description_clean, r.supermarket)
            for r in conn.execute(text(
                "SELECT description_clean, supermarket FROM silver.bodega.products"
            ))
        }
        new_items = [
            r for r in conn.execute(text(
                "SELECT DISTINCT description_clean, supermarket FROM silver.bodega.invoice_items"
            ))
            if (r.description_clean, r.supermarket) not in existing
        ]

    if not new_items:
        return

    batch_size = 30
    for i in range(0, len(new_items), batch_size):
        batch = new_items[i : i + batch_size]
        descs = [r.description_clean for r in batch]
        categorized = _categorize_batch(descs, api_key, model_id)
        for row, cat in zip(batch, categorized):
            yield {
                "description_clean": row.description_clean,
                "supermarket":       row.supermarket,
                "category":          cat.get("category", "OTHER"),
                "subcategory":       cat.get("subcategory", "")[:30],
                "is_weighted":       cat.get("is_weighted", False),
                "categorized_at":    datetime.now(timezone.utc).isoformat(),
                "llm_model":         model_id,
            }
```

**Required dependency**: `httpx>=0.27` in `workflows/dlt/pyproject.toml`.

---

## 7. Gold Layer

### Design decisions

**All Gold tables are SQL aggregations** over Silver tables.

**`gold.bodega.category_spending` is the primary dashboard table** because Silver has the LLM-derived `category`. This is the most valuable table for spend analysis.

**Weekly grain as the primary time bucket**: Daily spend is noisy (some days no shopping). Weekly is the right granularity for trend analysis.

**`gold.bodega.price_trends` only for repeat items**: price evolution is only meaningful if a product appears in ≥2 invoices. The model filters `purchase_count >= 2` to avoid noise.

**No pre-aggregated per-invoice Gold**: Superset can handle ad-hoc per-invoice queries directly against `silver.bodega.invoices`. Gold pre-aggregates only what Superset can't do efficiently.

---

### Table: `gold.bodega.spending_by_day`

- **Strategy**: incremental by time range on `invoice_date`
- **Grain**: `(invoice_date, supermarket)`

```sql
SELECT
    invoice_date,
    supermarket,
    COUNT(*)              AS invoice_count,
    SUM(total_amount)     AS total_amount,
    SUM(total_tax_amount) AS total_tax,
    SUM(item_count)       AS total_items,
    AVG(total_amount)     AS avg_basket_amount
FROM silver.bodega.invoices
GROUP BY invoice_date, supermarket
```

---

### Table: `gold.bodega.spending_by_week`

- **Strategy**: full refresh

```sql
SELECT
    date_trunc('week', invoice_date)  AS week_start,
    year(invoice_date)                AS year,
    week(invoice_date)                AS week_number,
    supermarket,
    COUNT(*)                          AS invoice_count,
    SUM(total_amount)                 AS total_amount,
    SUM(total_tax_amount)             AS total_tax,
    SUM(item_count)                   AS total_items,
    AVG(total_amount)                 AS avg_basket_amount,
    MAX(total_amount)                 AS max_basket_amount
FROM silver.bodega.invoices
GROUP BY
    date_trunc('week', invoice_date),
    year(invoice_date),
    week(invoice_date),
    supermarket
```

---

### Table: `gold.bodega.top_products`

- **Strategy**: full refresh

```sql
SELECT
    i.description_clean,
    p.category,
    p.subcategory,
    p.is_weighted,
    i.supermarket,
    COUNT(DISTINCT i.invoice_number)   AS purchase_count,
    SUM(i.quantity)                    AS total_quantity,
    SUM(i.total_amount)                AS total_spent,
    AVG(i.unit_price)                  AS avg_unit_price,
    MIN(i.unit_price)                  AS min_unit_price,
    MAX(i.unit_price)                  AS max_unit_price,
    MAX(i.invoice_date)                AS last_purchased_date
FROM silver.bodega.invoice_items i
LEFT JOIN silver.bodega.products p
    ON  i.description_clean = p.description_clean
    AND i.supermarket        = p.supermarket
GROUP BY i.description_clean, p.category, p.subcategory, p.is_weighted, i.supermarket
```

---

### Table: `gold.bodega.price_trends`

Weekly price evolution. Only products seen ≥2 times.

- **Strategy**: incremental by time range on `week_start`
- **Grain**: `(description_clean, supermarket, week_start)`

```sql
WITH weekly AS (
    SELECT
        description_clean,
        supermarket,
        date_trunc('week', invoice_date)  AS week_start,
        AVG(unit_price)                   AS avg_unit_price,
        COUNT(*)                          AS purchase_count
    FROM silver.bodega.invoice_items
    GROUP BY description_clean, supermarket, date_trunc('week', invoice_date)
),
repeat_products AS (
    SELECT description_clean, supermarket
    FROM silver.bodega.invoice_items
    GROUP BY description_clean, supermarket
    HAVING COUNT(*) >= 2
)
SELECT w.*, p.category, p.subcategory
FROM weekly w
JOIN repeat_products r USING (description_clean, supermarket)
LEFT JOIN silver.bodega.products p USING (description_clean, supermarket)
```

---

### Table: `gold.bodega.category_spending`

**The primary dashboard table.** Spending breakdown by LLM-assigned category.

- **Strategy**: incremental by time range on `invoice_date`
- **Grain**: `(invoice_date, category, supermarket)`

```sql
SELECT
    i.invoice_date,
    date_trunc('week',  i.invoice_date)  AS week_start,
    date_trunc('month', i.invoice_date)  AS month_start,
    COALESCE(p.category, 'OTHER')        AS category,
    p.subcategory,
    i.supermarket,
    COUNT(DISTINCT i.invoice_number)     AS invoice_count,
    COUNT(*)                             AS item_count,
    SUM(i.total_amount)                  AS total_spent
FROM silver.bodega.invoice_items i
LEFT JOIN silver.bodega.products p
    ON  i.description_clean = p.description_clean
    AND i.supermarket        = p.supermarket
GROUP BY
    i.invoice_date,
    date_trunc('week',  i.invoice_date),
    date_trunc('month', i.invoice_date),
    COALESCE(p.category, 'OTHER'),
    p.subcategory,
    i.supermarket
```

---

### Table: `gold.bodega.tax_summary`

- **Strategy**: incremental by time range on `month_start`
- **Grain**: `(month_start, tax_rate, supermarket)`

```sql
SELECT
    date_trunc('month', invoice_date)  AS month_start,
    tax_rate,
    supermarket,
    SUM(base_amount)                   AS base_amount,
    SUM(tax_amount)                    AS tax_amount
FROM silver.bodega.invoice_taxes
GROUP BY date_trunc('month', invoice_date), tax_rate, supermarket
```

---

## 8. Pipeline Configuration

### dlt (`workflows/dlt/`)

Environment variables follow the same pattern as `example_db/config.py`. Env-driven, no hardcoded values.

```python
# workflows/dlt/bodega/config.py
import os

KAFKA_BOOTSTRAP_SERVERS = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
KAFKA_TOPIC_BODEGA      = os.environ.get("KAFKA_TOPIC_BODEGA", "bodega_invoices")
OPENROUTER_API_KEY      = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL        = os.environ.get("OPENROUTER_MODEL", "xiaomi/mimo-v2.5:nitro")
TRINO_DSN               = os.environ["TRINO_DSN"]  # for enrich step to read silver tables
```

### dbt (`workflows/dbt/bodega/`)

`profiles.yml` follows the same `homelab` / `local` target pattern as `example_db`:

- **homelab**: Trino connector, catalogs `bronze`/`silver`/`gold` via Polaris/S3
- **local**: DuckDB files `bronze.duckdb`, `silver.duckdb`, `gold.duckdb` (shared dir via `DBT_DUCKDB_DIR`)

`dbt_project.yml` sets `+database` per medallion layer and schema `bodega`, yielding `<catalog>.bodega.<table>`.

---

## 9. Airflow DAG: `bodega_daily`

File: `workflows/airflow/dags/bodega_dag.py`

Pattern follows `example_db_dag.py`. Four tasks in dependency order.

```python
BODEGA_ENV_VARS = {
    **COMMON_ENV_VARS,
    "KAFKA_BOOTSTRAP_SERVERS": (
        "datahub-local-core-data-redpanda-0.datahub-local-core-data-redpanda.data.svc.cluster.local:9093,"
        "datahub-local-core-data-redpanda-1.datahub-local-core-data-redpanda.data.svc.cluster.local:9093,"
        "datahub-local-core-data-redpanda-2.datahub-local-core-data-redpanda.data.svc.cluster.local:9093"
    ),
    "KAFKA_TOPIC_BODEGA": "bodega_invoices",
}
BODEGA_SECRET_ENV_VARS = (
    *COMMON_SECRET_ENV_VARS,
    SecretEnvVarRef(secret_name="openrouter-credentials", secret_key="api_key", env_name="OPENROUTER_API_KEY"),
)

with DAG(dag_id="bodega_daily", schedule="0 8 * * *", ...):
    ingest = create_dlt_task(DltTaskConfig(
        task_id="dlt_ingest_bodega",
        pipeline_name="ingest",
        project_name="bodega",
        env_vars=BODEGA_ENV_VARS,
        secret_env_vars=COMMON_SECRET_ENV_VARS,
    ))
    dbt_silver = create_dbt_task(DbtTaskConfig(
        task_id="dbt_silver_bodega",
        project_name="bodega",
        select="silver.*",
        env_vars=COMMON_ENV_VARS,
        secret_env_vars=COMMON_SECRET_ENV_VARS,
    ))
    enrich = create_dlt_task(DltTaskConfig(
        task_id="dlt_enrich_bodega_products",
        pipeline_name="enrich",
        project_name="bodega",
        env_vars=BODEGA_ENV_VARS,
        secret_env_vars=BODEGA_SECRET_ENV_VARS,
    ))
    dbt_gold = create_dbt_task(DbtTaskConfig(
        task_id="dbt_gold_bodega",
        project_name="bodega",
        select="gold.*",
        env_vars=COMMON_ENV_VARS,
        secret_env_vars=COMMON_SECRET_ENV_VARS,
    ))

    ingest >> dbt_silver >> enrich >> dbt_gold
```

**Kubernetes Secret needed**: `openrouter-credentials` with key `api_key`.

---

## 10. New Docker Image Dependencies

Add to `workflows/dlt/pyproject.toml`:

```toml
[project.optional-dependencies]
bodega = [
  "confluent-kafka>=2.5",
  "httpx>=0.27",
]
```

Update `workflows/dlt/Dockerfile` to install these (or merge into the main dependency group).

---

## 11. Superset Dashboard: Bodega

Connect Superset to the Iceberg catalog via the existing Trino endpoint. One dataset per Gold table.

| Chart                          | Type           | Dataset                         | Key metric                                           |
| ------------------------------ | -------------- | ------------------------------- | ---------------------------------------------------- |
| Weekly spend trend             | Line           | `gold.bodega.spending_by_week`  | `total_amount` by `week_start`                       |
| Monthly spend heatmap          | Calendar       | `gold.bodega.spending_by_day`   | `total_amount`                                       |
| Spend by category (this month) | Pie / Treemap  | `gold.bodega.category_spending` | `total_spent` by `category`                          |
| Category trend over time       | Stacked area   | `gold.bodega.category_spending` | `total_spent` by `week_start` + `category`           |
| Top 20 products (amount)       | H-bar          | `gold.bodega.top_products`      | `total_spent`                                        |
| Top 20 products (frequency)    | H-bar          | `gold.bodega.top_products`      | `purchase_count`                                     |
| Price evolution                | Line + filter  | `gold.bodega.price_trends`      | `avg_unit_price` by `week_start` (filter by product) |
| Tax breakdown by month         | Stacked bar    | `gold.bodega.tax_summary`       | `tax_amount` by `tax_rate`                           |
| Average basket size            | Dual-axis line | `gold.bodega.spending_by_week`  | `avg_basket_amount` + `total_items`                  |

Apply a global date-range filter to all charts.

---

## 12. Phased Delivery

| Phase  | Deliverable                                                        | Effort  |
| ------ | ------------------------------------------------------------------ | ------- |
| **P0** | Kafka topic, dlt/dbt project scaffolds, config                     | 0.5 day |
| **P1** | `bronze.bodega.raw_invoices` dlt ingest pipeline + Docker deps     | 1 day   |
| **P2** | Silver SQL tables (invoices, invoice_items, invoice_taxes, stores) | 1 day   |
| **P3** | `silver.bodega.products` LLM enrichment dlt pipeline               | 1 day   |
| **P4** | All Gold SQL tables                                                | 1 day   |
| **P5** | Airflow DAG + Kubernetes Secret                                    | 0.5 day |
| **P6** | Superset datasets + dashboard                                      | 1 day   |

---

## 13. Remaining Open Questions

| #   | Question                                                           | Status                                                                                                                   | Impact                       |
| --- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------- |
| 1   | Kafka broker addresses                                             | ✅ Resolved — 3 brokers at port 9093, no auth                                                                             | See Section 2                |
| 2   | Which data lands in Kafka: raw or parsed JSON?                     | ✅ Resolved — parsed invoice JSON from `parse_mercadona_invoice`, see [schema](../agents/n8n/schemas/bodega_invoice.schema.json) | Bronze flatten function done |
| 3   | OpenRouter model ID                                                | ✅ Resolved — `xiaomi/mimo-v2.5:nitro`, parameterised via `OPENROUTER_MODEL`                                              |                              |
| 4   | `confluent-kafka` in dlt Kubernetes pod                            | ⚠️ Open — test at P1; fallback to `kafka-python` if native lib fails                                                      | Bronze pipeline runtime      |
| 5   | Backfill: 1 year of emails in Kafka already?                       | ⚠️ Open — `bodega_invoices` topic doesn't exist yet; n8n must re-run with extended `MAX_DAYS`                             | First-run strategy           |
| 6   | dbt `--select silver.*` / `--select gold.*` syntax for split tasks | ⚠️ Open — verify dbt node selector works with catalog-qualified model paths                                               | Airflow DAG design           |
