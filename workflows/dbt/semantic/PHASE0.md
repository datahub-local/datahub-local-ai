# Phase 0 — measured definitions

Each metric in `bodega.yaml` was defined by running its SQL against the live
homelab Trino (v480) as user `mcp`, over `silver.bodega` / `gold.bodega`. This
file records **what was found**, and the query that finds it again.

**No figures here, deliberately.** The bodega tables hold personal purchase
history, so a number written down is that data committed to git — and it would
be stale the next time the ingest runs anyway. Every finding below is stated as
a direction or an invariant, which is the durable part; run the query beside it
to get the current value. The same rule governs `bodega.yaml`: an `excludes`
states what a metric leaves out, which is a property of the definition, never
of today's rows.

First measured 2026-09-04, re-measured in full 2026-09-05 after the table grew
by roughly a seventh. **Every finding held.** A finding that reverses is the
interesting outcome and belongs in this file.

Everything here is one supermarket and one payment method, which is why several
`excludes` clauses are about absent variety rather than about disagreement.

## The headline reconciliation

The spec (§4.2, §9) predicted that `grocery_spend_eur` and `category_spend_eur`
**cannot agree**, because invoice-level rounding and an `OTHER` bucket pull them
apart. **They agree exactly** — to the cent, on both measurement dates.

```sql
WITH g AS (SELECT sum(total_amount) AS v FROM silver.bodega.invoices),
     c AS (SELECT sum(total_spent)  AS v FROM gold.bodega.category_spending),
     i AS (SELECT sum(total_amount) AS v FROM silver.bodega.invoice_items)
SELECT round(g.v,2), round(i.v,2), round(c.v,2), round(c.v - g.v, 2) FROM g, c, i;
```

Stronger than the aggregate: the header total equals the sum of its own lines on
**every invoice**, to the cent. The query returns the number compared, the number
mismatching (zero) and the largest absolute difference (zero).

```sql
WITH h AS (SELECT invoice_number, total_amount FROM silver.bodega.invoices),
     l AS (SELECT invoice_number, sum(total_amount) AS items_total
           FROM silver.bodega.invoice_items GROUP BY invoice_number)
SELECT count(*), sum(CASE WHEN abs(h.total_amount - l.items_total) > 0.005 THEN 1 ELSE 0 END),
       max(abs(h.total_amount - l.items_total))
FROM h JOIN l ON h.invoice_number = l.invoice_number;
```

**Why they agree, and why that is not a licence to treat them as one metric.**
The two mechanisms the spec named are real but currently measure zero here:

- *Invoice-level rounding*: this retailer's receipts happen to have line totals
  that sum exactly to the header. This is a property of the parsed source, not an
  invariant the pipeline enforces. A supermarket that rounds, or a receipt
  carrying a basket-level discount, reintroduces the gap with no code change.
- *The `OTHER` bucket*: it exists and holds a rounding-error share of spend, and
  no product has ever been `PARSE_ERROR`. The bucket does not currently move the
  total because categorisation happened to cover everything. The `LEFT JOIN` in
  `category_spending.sql` means an *uncategorised* line still contributes its
  spend under `OTHER` rather than being dropped, which is what keeps the totals
  equal — so the agreement survives a categorisation gap but not a rounding one.

So the `excludes` text keeps the warning, restated as measured: the two are
equal **today**, they are not equal *by construction*, and the grain differs
(per-trip vs per-line). A non-zero gap is a finding about the source, not
necessarily a registry bug.

## The ratio trap, quantified

`AVG(unit_price)` and `SUM(total)/SUM(quantity)` are different numbers, and only
the second is `blended_unit_price_eur`. The first — what `top_products.sql`
computes — has come out **several percent higher** on every measurement. The
compiler must never emit it.

```sql
SELECT round(avg(unit_price),4), round(sum(total_amount)/nullif(sum(quantity),0),4)
FROM silver.bodega.invoice_items;
```

Unit composition confirms the no-fixed-unit hazard: both `KG` and `EA` lines are
always present, `EA` far outnumbering `KG`, so the blended figure mixes EUR/kg
with EUR/unit exactly as `price_trends.sql` intends. No line has `quantity` 0 or
null, so nothing is currently dropped by the division — but the `nullif` stays,
because one such row would otherwise fail the whole query.

```sql
SELECT unit, count(*) FROM silver.bodega.invoice_items GROUP BY unit;
```

## Findings the spec did not have

1. **`price_trends` silently drops a double-digit share of spend.** Its
   `HAVING COUNT(*) >= 2` keeps only repeat-purchased products — roughly half of
   them, and with them a double-digit percentage of total spend, on every
   measurement. No `excludes` in the spec mentioned this. Any metric sourced from
   `price_trends` must state it. This registry therefore sources
   `blended_unit_price_eur` from `invoice_items` instead, where nothing is
   filtered out.

   ```sql
   SELECT (SELECT count(DISTINCT description_clean) FROM silver.bodega.invoice_items),
          (SELECT count(DISTINCT description_clean) FROM gold.bodega.price_trends),
          (SELECT sum(total_amount) FROM silver.bodega.invoice_items),
          (SELECT sum(total_spent)  FROM gold.bodega.price_trends);
   ```

2. **No returns exist in the data.** No negative line amounts, no negative
   quantities, every line strictly positive.
   `grocery_spend_eur.excludes` claims returns are "included as whatever sign the
   receipt carried"; that is untested, not observed. Stated as unobserved rather
   than as behaviour.

   ```sql
   SELECT count(*) FROM silver.bodega.invoice_items
   WHERE total_amount < 0 OR quantity < 0;
   ```

3. **Tax is inside the total, verifiably.** `total_tax_amount` plus
   `total_base_amount` equals the receipt total exactly. "VAT included" is
   measured, not assumed.

   ```sql
   SELECT round(sum(total_tax_amount) + sum(total_base_amount) - sum(total_amount), 2)
   FROM silver.bodega.invoices;
   ```

4. **`avg_basket_eur` is unambiguous on this data.** `sum/count` and `avg()` give
   the same figure because there is exactly one row per invoice. The ratio form is
   still the compiled one — the equality is a property of the grain, and it breaks
   the moment a metric is averaged over anything pre-aggregated.

5. **The data is stale by days, not hours.** The last invoice predates any given
   measurement, because ingest runs on receipt arrival. The partial-period flag is
   therefore exercised by real data on any query whose window reaches the present,
   which makes it testable rather than theoretical.

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

One consequence for the build: `mcp-semantic` can send `X-Trino-User: mcp` and
needs no credential, keeping the deployment secret-free as it is today.

**The planned narrowing is not happening.** Phase 3 was going to cut `mcp` from
six catalogs down to `silver|gold`; that was dropped deliberately. The chart
manages three permission tiers, not per-user grants — `admin` (all), a
read-write tier (`dbt`, `superset`, `maintenance`) and a read-only tier (`mcp`)
— and users are assigned to a tier rather than given bespoke rules. A
`silver|gold`-only grant would be a fourth tier existing for one user.

That costs nothing real, because the boundary was never the Trino user. It is
the NetworkPolicy plus the absence of any `run_sql` tool: the semantic server
composes every statement in code from a validated registry, so a narrower grant
removes no capability the agent can actually reach.

Read the live rules before assuming any user works; the set has changed at least
once and the file above is a copy, not the source:

```bash
kubectl get cm datahub-local-core-data-trino-trino-access-control-volume-coordinator \
  -n data -o jsonpath='{.data.rules\.json}' | python3 -m json.tool
```
