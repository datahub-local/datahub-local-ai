{# The balance series, labelled for charts: one row per account/date/type with the masked
   IBAN and institution attached. The account label is joined rather than copied so a
   relabelled account does not leave stale strings in the series. #}
SELECT
    b.account_id,
    b.balance_date,
    b.balance_type,
    b.amount,
    b.currency,
    a.iban_masked,
    a.institution_id
FROM {{ ref('balances') }} AS b
LEFT JOIN {{ ref('accounts') }} AS a
    ON a.account_id = b.account_id
