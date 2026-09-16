# Finance dashboard

Single-tab Superset dashboard over the finance dbt silver/gold layers
(`workflows/dbt/projects/finance`), reading Trino catalog `gold`, schema
`finance` (the `transactions` dataset is **virtual** and reads
`silver.finance.transactions` cross-catalog from the gold connection, because
the gold marts are monthly aggregates and carry no per-payee detail).

| Tab | Charts | Datasets |
|---|---|---|
| Overview | monthly inflow vs outflow (stacked bar) · monthly spend by category (stacked bar) · account balance series (line) · top payees (aggregate table) | `monthly_category_spend`, `account_balance_series`, `transactions` (virtual) |

Native filters (scope: all charts): date range (default *Last year*), bank
(`institution_id`) and category, both on `monthly_category_spend`. Scope is
`ROOT_ID` on purpose: a hand-written export carries no `chartsInScope`, and
without it Superset ignores `rootPath`/`excluded`; effective scoping comes from
column matching — the balance series carries its own `institution_id` from a
different dataset and is left unfiltered rather than narrowed.

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
  can rank payees; it joins nothing — categories live in the gold aggregates.
