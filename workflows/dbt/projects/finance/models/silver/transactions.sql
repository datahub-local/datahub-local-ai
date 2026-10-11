{# Transactions as typed, analysis-ready rows. The account's masked IBAN is joined from
   silver.accounts rather than taken from the row, because a transaction payload carries
   its own account only as an opaque uid - the human-readable label lives on the account.

   payee is the best human label. payee_clean is the ENRICH JOIN KEY, and for card
   purchases the bank supplies no counterparty at all - the remittance text is the whole
   template `... COMPRA EN <merchant>, CON LA TARJETA : ... EL <date>`, so the raw text
   would be unique per transaction (a different date each day) and the LLM would
   categorise every row separately, never reusing a merchant. The card template's
   merchant is therefore extracted first; anything that does not match the template
   falls back to the raw label. This is a text heuristic over one bank's wording, so it
   is kept here in Silver (presentation), never in the adapter (wire format).

   One row per payment. A bank whose reference is a booking-date-scoped ordinal
   (the adapter's shape rule) has had two identities for the same payment at
   different times - the ordinal it first landed under, and the hash minted after
   the identity rule changed - so both rows are in bronze and both would reach
   this layer. They are ranked on the payment key the hash itself is built from
   and the non-positional row wins; a positional row survives only when it is the
   only copy of that payment, which is the case for anything booked before the
   re-fetch window. #}
WITH ranked AS (
    SELECT
        t.*,
        ROW_NUMBER() OVER (
            PARTITION BY
                t.provider,
                t.account_id,
                t.booking_date,
                t.amount,
                t.currency,
                COALESCE(t.remittance_info, ''),
                COALESCE(NULLIF(trim(t.creditor_name), ''), NULLIF(trim(t.debtor_name), ''))
            ORDER BY
                CASE WHEN {{ finance_is_positional_id("t.stable_id") }} THEN 1 ELSE 0 END,
                t._ingested_at DESC
        ) AS payment_rank
    FROM {{ source('finance', 'raw_transactions') }} AS t
)
SELECT
    t.provider,
    t.account_id,
    t.stable_id,
    t.institution_id,
    CAST(t.booking_date AS DATE)                                        AS booking_date,
    TRY_CAST(t.value_date AS DATE)                                      AS value_date,
    CAST(t.amount AS DECIMAL(18, 2))                                    AS amount,
    CASE WHEN CAST(t.amount AS DECIMAL(18, 2)) < 0 THEN 'outflow' ELSE 'inflow' END AS direction,
    t.currency,
    COALESCE(
        NULLIF(trim(t.creditor_name), ''),
        NULLIF(trim(t.debtor_name), ''),
        NULLIF(trim(t.remittance_info), '')
    )                                                                   AS payee,
    CASE
        WHEN NULLIF(trim(regexp_extract(t.remittance_info, '(?i)COMPRA EN (.*?), CON LA TARJETA', 1)), '') IS NOT NULL
            THEN {{ finance_clean_key("regexp_extract(t.remittance_info, '(?i)COMPRA EN (.*?), CON LA TARJETA', 1)") }}
        ELSE {{ finance_clean_key("COALESCE(NULLIF(trim(t.creditor_name), ''), NULLIF(trim(t.debtor_name), ''), NULLIF(trim(t.remittance_info), ''))") }}
    END                                                                 AS payee_clean,
    t.creditor_name,
    t.debtor_name,
    t.creditor_iban,
    t.debtor_iban,
    t.bank_transaction_code,
    t.remittance_info,
    a.iban_masked,
    t._ingested_at
FROM ranked AS t
LEFT JOIN {{ ref('accounts') }} AS a
    ON a.account_id = t.account_id
WHERE t.payment_rank = 1
