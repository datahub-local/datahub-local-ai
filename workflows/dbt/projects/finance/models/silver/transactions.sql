{# Transactions as typed, analysis-ready rows. The account's masked IBAN is joined from
   silver.accounts rather than taken from the row, because a transaction payload carries
   its own account only as an opaque uid - the human-readable label lives on the account. #}
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
    {{ finance_clean_key("COALESCE(NULLIF(trim(t.creditor_name), ''), NULLIF(trim(t.debtor_name), ''), NULLIF(trim(t.remittance_info), ''))") }} AS payee_clean,
    t.creditor_name,
    t.debtor_name,
    t.creditor_iban,
    t.debtor_iban,
    t.bank_transaction_code,
    t.remittance_info,
    a.iban_masked,
    t._ingested_at
FROM {{ source('finance', 'raw_transactions') }} AS t
LEFT JOIN {{ ref('accounts') }} AS a
    ON a.account_id = t.account_id
