{# Balance snapshots reduced to the latest reading per account/date/type. Balance type is
   part of the key: Enable Banking can return several for one day (closing booked,
   available, ...), and collapsing them would silently drop all but one. Bronze already
   merges on (account_id, balance_type, reference_date) with the ingestion date standing
   in when reference_date is NULL; the ranking here is the backstop for older loads. #}
WITH dated AS (
    SELECT
        account_id,
        balance_type,
        CAST(amount AS DECIMAL(18, 2))  AS amount,
        currency,
        COALESCE(TRY_CAST(reference_date AS DATE), {{ finance_iso_date('_ingested_at') }}) AS balance_date,
        _ingested_at
    FROM {{ source('finance', 'raw_balances') }}
),

ranked AS (
    SELECT
        account_id,
        balance_type,
        amount,
        currency,
        balance_date,
        _ingested_at,
        ROW_NUMBER() OVER (
            PARTITION BY account_id, balance_date, balance_type
            ORDER BY _ingested_at DESC
        ) AS snapshot_rank
    FROM dated
)

SELECT
    account_id,
    balance_date,
    balance_type,
    amount,
    currency,
    _ingested_at
FROM ranked
WHERE snapshot_rank = 1
