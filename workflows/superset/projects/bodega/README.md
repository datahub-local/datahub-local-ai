# Bodega dashboard

Six-tab Superset dashboard over the bodega dbt gold layer
(`workflows/dbt/projects/bodega`), reading Trino catalog `gold`, schema `bodega`.

| Tab | Charts | Datasets |
|---|---|---|
| Overview | 4 KPI tiles (spent, trips, avg basket, items) · weekly spend line · avg basket by weekday · monthly spend stacked by supermarket | `spending_by_day`, `spending_by_week` |
| Categories | monthly spend stacked by category · category totals (horizontal bar) · top subcategories table | `category_spending` |
| Products | top products by spend (horizontal bar) · most frequently bought table · product price history line · purchase history table (drill-down via product click) | `product_purchases` (virtual) |
| Prices | staple prices €/kg line · staple prices €/unit line · staples-vs-first-purchase KPI · biggest price moves table | `price_trends`, `price_index`, `price_movers` (virtual) |
| Taxes | monthly VAT stacked by rate · VAT totals table | `tax_summary` |
| Invoices | invoice list table · one-row invoice summary table · line-items table · items by spend (horizontal bar) · spend by category (horizontal bar) | `invoice_list`, `invoice_lines` (virtual) |

Native filters (scope: all tabs): date range (default *Last year*), supermarket,
category, and **Invoice** (single-select on `invoice_label`). All filters are
scoped `ROOT_ID` on purpose: hand-written export YAML carries no `chartsInScope`
(the UI computes and saves it), and without it Superset ignores
`rootPath`/`excluded` and falls back to *all charts*. Effective scoping comes
from column matching instead — the Invoice filter only bites on the two invoice
datasets, since nothing else has `invoice_label` (other charts just show the
"filter not applied" badge while an invoice is selected).

Invoice drill-down works through `invoice_label` (`2026-06-26 12:01 MERCADONA`),
a byte-identical string computed in **both** invoice datasets (datetime to the
minute + supermarket — unique in practice, no visible invoice id). Superset
table cross-filters always emit *clicked column = cell value*, so the label is
the one clickable identity. The list runs in **aggregate** mode:
`invoice_label` is the only dimension (clicking it filters the drill-down to
that invoice), while Items/Total/Tax are `MAX()` metrics — metric cells never
emit cross-filters, so a stray click is a no-op instead of mis-filtering. Rows
sort newest-first through a non-displayed `MAX(invoice_datetime)` sort metric.
The summary strip is a one-row aggregate table on `invoice_list` (shop,
address, phone, payment, totals) where every metric is
`max_by(field, invoice_datetime)`, so all cells describe the same, newest
matching invoice — with no selection that is the newest invoice in range (the
leading Invoice column says which). It is deliberately **not** a Handlebars
card: Handlebars compiles templates with `new Function`, which Superset's
default CSP (`script-src` without `'unsafe-eval'`) blocks.

Notes:

- Prices are the blended `price` column of `gold.bodega.price_trends`
  (`total spent / total quantity`): receipts print €/kg for weighed lines and
  €/unit otherwise, so the two staple-price charts split on `is_weighted` (LLM
  enrichment) to keep each axis in one dimension. `price_index` and
  `price_movers` are **virtual datasets** over the same table: the KPI indexes
  each product to 100 at its first observed week, the movers table compares
  first vs. last observed price.
- The Products tab mirrors the Invoices drill-down: the frequent-products table
  runs in aggregate mode (`description_clean` is the only clickable dimension)
  and the top-products bar emits the same column, so clicking either filters
  the price/purchase-history charts below via cross-filtering.
- The `weekday` column on `spending_by_day` is a calculated column
  (`'1 Mon' … '7 Sun'`) so weekday bars sort chronologically.
- The average basket metric is `SUM(total_amount) / SUM(invoice_count)` — never
  an average of daily averages.
- `invoice_list` and `invoice_lines` are **virtual datasets** over the silver
  layer (`silver.bodega.invoices` / `silver.bodega.invoice_items`, cross-catalog
  from the gold connection) because the gold marts are aggregated and carry no
  per-invoice detail; `invoice_lines` joins `silver.bodega.products` for the
  LLM-assigned category and `invoice_list` joins `silver.bodega.stores` for the
  store address and phone shown in the summary card.
