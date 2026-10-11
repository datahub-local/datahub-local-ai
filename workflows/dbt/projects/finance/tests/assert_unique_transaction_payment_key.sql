-- One row per payment in the curated layer. A payment is identified by the values
-- the hash identity is built from, so a bank whose reference is a positional
-- ordinal cannot leave the ordinal row and its hash twin both in silver - which
-- is how the Actual sync came to import every payment twice (2026-10-11).
--
-- Rows returned by this query are payments that still carry more than one row;
-- the model in models/silver/transactions.sql is expected to return none.
SELECT
    provider,
    account_id,
    booking_date,
    amount,
    currency,
    remittance_info,
    COALESCE(NULLIF(trim(creditor_name), ''), NULLIF(trim(debtor_name), '')) AS counterparty,
    COUNT(*)                                                                AS rows_for_one_payment,
    COUNT(DISTINCT stable_id)                                               AS distinct_identities
FROM {{ ref('transactions') }}
GROUP BY 1, 2, 3, 4, 5, 6, 7
HAVING COUNT(*) > 1
