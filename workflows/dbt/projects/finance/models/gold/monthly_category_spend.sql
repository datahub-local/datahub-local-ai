{# Spend and inflow per month x category x institution x direction. The category comes
   from the LLM enrich step, keyed on payee_clean; a payee the model has not seen keeps
   an UNCATEGORISED row rather than vanishing from the total. Amounts are reported as
   positive magnitudes and separated by `direction`, so a chart never nets a refund
   against a purchase. #}
WITH categories AS (
    -- merchant_categories is merge-by-key in dlt but the Iceberg filesystem destination
    -- can fall back to append, so dedupe to the latest categorisation per payee
    SELECT
        payee_clean,
        max_by(category, categorized_at)    AS category
    FROM {{ source('finance_enrich', 'merchant_categories') }}
    GROUP BY payee_clean
)

SELECT
    CAST(date_trunc('month', t.booking_date) AS DATE)   AS month_start,
    COALESCE(c.category, 'UNCATEGORISED')               AS category,
    t.institution_id,
    t.direction,
    t.currency,
    SUM(ABS(t.amount))                                  AS amount,
    COUNT(*)                                            AS transaction_count
FROM {{ ref('transactions') }} AS t
LEFT JOIN categories AS c
    ON c.payee_clean = t.payee_clean
GROUP BY
    CAST(date_trunc('month', t.booking_date) AS DATE),
    COALESCE(c.category, 'UNCATEGORISED'),
    t.institution_id,
    t.direction,
    t.currency
