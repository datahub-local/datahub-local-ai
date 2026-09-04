# Phase 0 — measured definitions

Every number below was read from the live homelab Trino (v480) on 2026-09-04
against `silver.bodega` / `gold.bodega`, as user `mcp`. Reproduce with the
queries inline; each is the definition of the metric beside it.

Data at measurement time: **75 invoices, 1481 line items, 428 products,
2026-01-05 to 2026-08-19**. Everything here is one supermarket (MERCADONA) and
one payment method (TARJETA BANCARIA), which is why several `excludes` clauses
are about absent variety rather than about disagreement.

## The headline reconciliation

The spec (§4.2, §9) predicted that `grocery_spend_eur` and `category_spend_eur`
**cannot agree**, because invoice-level rounding and an `OTHER` bucket pull them
apart. On this data they agree exactly:

| Quantity | Source | Value |
|----------|--------|-------|
| `grocery_spend_eur` | `sum(total_amount)` from `silver.bodega.invoices` | **4086.96** |
| line-item sum | `sum(total_amount)` from `silver.bodega.invoice_items` | **4086.96** |
| `category_spend_eur` | `sum(total_spent)` from `gold.bodega.category_spending` | **4086.96** |

Gap: **0.00 EUR / 0.0000%**.

```sql
WITH g AS (SELECT sum(total_amount) AS v FROM silver.bodega.invoices),
     c AS (SELECT sum(total_spent)  AS v FROM gold.bodega.category_spending),
     i AS (SELECT sum(total_amount) AS v FROM silver.bodega.invoice_items)
SELECT round(g.v,2), round(i.v,2), round(c.v,2), round(c.v - g.v, 2) FROM g, c, i;
```

Stronger than the aggregate: the header total equals the sum of its own lines on
**every one of the 75 invoices**, to the cent.

```sql
-- 75 compared, 0 mismatching, max abs diff 0.0
WITH h AS (SELECT invoice_number, total_amount FROM silver.bodega.invoices),
     l AS (SELECT invoice_number, sum(total_amount) AS items_total
           FROM silver.bodega.invoice_items GROUP BY invoice_number)
SELECT count(*), sum(CASE WHEN abs(h.total_amount - l.items_total) > 0.005 THEN 1 ELSE 0 END),
       max(abs(h.total_amount - l.items_total))
FROM h JOIN l ON h.invoice_number = l.invoice_number;
```

**Why they agree, and why that is not a licence to treat them as one metric.**
The two mechanisms the spec named are real but currently measure zero here:

- *Invoice-level rounding*: Mercadona's receipts happen to have line totals that
  sum exactly to the header. This is a property of the parsed source, not an
  invariant the pipeline enforces. A supermarket that rounds, or a receipt
  carrying a basket-level discount, reintroduces the gap with no code change.
- *The `OTHER` bucket*: it exists and holds **2 rows / 3.75 EUR**, and no product
  is `PARSE_ERROR` at all (0 of 428). The bucket does not currently move the
  total because categorisation happened to cover everything. The `LEFT JOIN` in
  `category_spending.sql` means an *uncategorised* line still contributes its
  spend under `OTHER` rather than being dropped, which is what keeps the totals
  equal — so the agreement survives a categorisation gap but not a rounding one.

So the `excludes` text keeps the warning, restated as measured: the two are
equal **today at 0.00%**, they are not equal *by construction*, and the grain
differs (per-trip vs per-line). Phase 4 compares them again; a non-zero gap is a
finding about the source, not necessarily a registry bug.

## The ratio trap, quantified

`AVG(unit_price)` and `SUM(total)/SUM(quantity)` are different numbers, and only
the second is `blended_unit_price_eur`:

| Expression | Value |
|------------|-------|
| `avg(unit_price)` — what `top_products.sql` computes | 2.5099 |
| `sum(total_amount)/nullif(sum(quantity),0)` — the metric | **2.3850** |

**5.2% apart.** The compiler must never emit the first form.

```sql
SELECT round(avg(unit_price),4), round(sum(total_amount)/nullif(sum(quantity),0),4)
FROM silver.bodega.invoice_items;
```

Unit composition confirms the no-fixed-unit hazard: **62 KG lines and 1419 EA
lines**, so the blended figure mixes EUR/kg with EUR/unit exactly as
`price_trends.sql` intends. No line has `quantity` 0 or null, so nothing is
currently dropped by the division — but the `nullif` stays, because one such row
would otherwise fail the whole query.

## Findings the spec did not have

1. **`price_trends` silently drops 12.9% of spend.** Its `HAVING COUNT(*) >= 2`
   keeps only repeat-purchased products: **220 of 428 products, 3557.78 of
   4086.96 EUR**. No `excludes` in the spec mentioned this. Any metric sourced
   from `price_trends` must state it. This registry therefore sources
   `blended_unit_price_eur` from `invoice_items` instead, where nothing is
   filtered out.

   ```sql
   SELECT (SELECT count(DISTINCT description_clean) FROM silver.bodega.invoice_items),
          (SELECT count(DISTINCT description_clean) FROM gold.bodega.price_trends),
          (SELECT sum(total_amount) FROM silver.bodega.invoice_items),
          (SELECT sum(total_spent)  FROM gold.bodega.price_trends);
   ```

2. **No returns exist in the data.** 0 negative line amounts, 0 negative
   quantities, line range 0.15 to 35.00. `grocery_spend_eur.excludes` claims
   returns are "included as whatever sign the receipt carried"; that is untested,
   not observed. Stated as unobserved rather than as behaviour.

3. **Tax is inside the total, verifiably.** `total_tax_amount` 414.69 +
   `total_base_amount` 3672.27 = 4086.96, the receipt total. "VAT included" is
   measured, not assumed.

4. **`avg_basket_eur` is unambiguous on this data.** `sum/count` and `avg()` both
   give **54.4928** because there is exactly one row per invoice
   (75 rows, 75 distinct invoice numbers). The ratio form is still the compiled
   one — the equality is a property of the grain, and it breaks the moment a
   metric is averaged over anything pre-aggregated.

5. **The data is 16 days stale** (last invoice 2026-08-19, measured 2026-09-04).
   The partial-period flag is therefore exercised by real data on any query whose
   window reaches the present, which makes it testable rather than theoretical.

## Access control, as actually configured

§5.4 of the spec says this Trino "requires no authentication" and that a user
name is "a label, not a credential", inferred from `SHOW CATALOGS` succeeding as
an invented user. **The live config is different and stricter**, and the
difference matters enough to record.

`access-control.name=file` is already enabled on the coordinator, with
`security.config-file=/etc/trino/access-control/rules.json`. That file has a
`"queries"` section listing users:

```json
"queries": [
  {"user": "admin", "allow": ["execute", "view", "kill"]},
  {"user": "mcp",   "allow": ["execute"]}
]
```

There is **no catch-all rule**, so an unknown user cannot execute at all.
Verified, both directions:

- as `semantic-phase0` (invented): `SHOW CATALOGS` -> `Access Denied: Cannot
  execute query`. The spec's premise does not reproduce.
- as `mcp` (asserted, no credential presented): full read access to
  `bronze|silver|gold|test|memory|postgresql_.*`.
- as `mcp`: `CREATE TABLE silver.bodega.semantic_probe_delete_me` ->
  `Access Denied: Cannot create table` (nothing was created).
- as `mcp`: `SELECT ... FROM system.runtime.queries` -> `Access Denied: Cannot
  access catalog system`.

Coordinator pod age at measurement: 30h, i.e. well past any config change, so
per §5.4's own rule these negatives are real and not stale-config artifacts.

**The conclusion the spec reaches is still right, by a different route.** A
known user name is impersonable — asserting `X-Trino-User: mcp` with no
credential is enough — so the user name remains *not* a credential. What changed
is that unknown names are denied rather than accepted, so the rules file is a
real reduction in blast radius and `read-only` on the catalogs is genuinely
enforced. The NetworkPolicy plus the absence of a SQL tool is still the
boundary; the Trino user name is now a weak second layer rather than none.

Two consequences for the build:

- `mcp-semantic` can send `X-Trino-User: mcp` and needs no credential, keeping
  `agents/mcp/` secret-free as it is today.
- Phase 3's planned rules change is smaller than the spec assumed: the catalog
  rule already denies `system` and allows only read. Narrowing `mcp` from all
  six catalogs down to `silver|gold` is the remaining work, and it still needs
  the coordinator restart, because `security.refresh-period=60s` does not
  reload this file.
