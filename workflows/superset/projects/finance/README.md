# Finance dashboard

Single-tab Superset dashboard over the finance dbt silver/gold layers
(`workflows/dbt/projects/finance`), reading Trino catalog `gold`, schema
`finance` (the `transactions` dataset is **virtual** and reads
`silver.finance.transactions` cross-catalog from the gold connection, because
the gold marts are monthly aggregates and carry no per-payee detail).

| Tab | Charts | Datasets |
|---|---|---|
| Overview | monthly inflow vs outflow (stacked bar) · monthly spend by category (stacked bar) · account balance series (line) · top payees (aggregate table) | `monthly_category_spend`, `account_balance_series`, `transactions` (virtual) |

Native filters (scope: `ROOT_ID`, all charts): date range (default *Last
year*), bank (`institution_id`) and category. Bank and category target the
column on **two** datasets — `monthly_category_spend` and the row-grain
`transactions` — because a native filter only reaches a chart whose dataset is
one of its targets: the top-payees table would otherwise never see them. The
balance series carries its own `institution_id` from a third dataset and is
left unfiltered rather than narrowed.

Notes:

- Amounts in `monthly_category_spend` are a positive magnitude split by
  `direction`, so a refund never nets against a purchase; the two bar charts
  filter `direction = outflow` (spend) or group by `direction` (flow).
- Top payees is an **aggregate** table grouped on `payee`: an aggregate table's
  metric cells never emit a cross-filter, unlike a raw-mode table where every
  cell emits its own value. Horizontal echarts bars are avoided for the same
  reason (their series is transposed and the x-axis cross-filter emits the
  metric value), so no `chart_configuration` exclusions are needed.
- The balance line groups by `iban_masked` **and** `balance_type`: a day can
  carry several ISO 20022 types (closing booked, available, ...) and collapsing
  them would silently drop all but one.
- The `transactions` virtual dataset is row grain and is the only dataset that
  can rank payees; it left-joins `silver.finance.merchant_categories` on
  `payee_clean` so the category filter reaches the table (`UNCATEGORISED` until
  enrich has seen the payee), and the chart pins `granularity_sqla:
  booking_date` so the dashboard date range applies — a table with no time
  column is not time-filtered at all.
