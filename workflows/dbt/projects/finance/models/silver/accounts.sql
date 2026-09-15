{# One row per account: the latest snapshot wins. The IBAN is masked here and nowhere
   else - bronze keeps the full one, and nothing user-facing reads bronze. #}
WITH ranked AS (
    SELECT
        provider,
        account_id,
        institution_id,
        '****' || substr(trim(iban), -4)                AS iban_masked,
        currency,
        status,
        _ingested_at,
        ROW_NUMBER() OVER (
            PARTITION BY provider, account_id
            ORDER BY _ingested_at DESC
        )                                               AS snapshot_rank
    FROM {{ source('finance', 'raw_accounts') }}
)
SELECT
    provider,
    account_id,
    institution_id,
    iban_masked,
    currency,
    status,
    _ingested_at
FROM ranked
WHERE snapshot_rank = 1
