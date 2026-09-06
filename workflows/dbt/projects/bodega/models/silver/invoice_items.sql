{#
  Location is denormalised from `stores` for the same reason as `invoices`: a semantic
  dimension must be a bare column on the metric's own model. The LEFT JOIN follows the
  UNNEST because the exploding join is a FROM-clause fragment against `b`, and it keys
  on the normalised address rather than `store_vat_id`, which is the chain's company VAT.
#}
WITH store_location AS (
    SELECT address_key, store_id, store_label, province, town, postal_code
    FROM {{ ref('stores') }}
)

SELECT
    b.invoice_number,
    CAST(_it.pos AS INTEGER)                                                       AS item_position,
    CAST({{ bodega_parse_dt('b.invoice_date') }} AS DATE)                          AS invoice_date,
    b.store_vat_id,
    b.supermarket,
    loc.store_id,
    COALESCE(loc.store_label, 'UNKNOWN')                                           AS store_label,
    COALESCE(loc.province, 'UNKNOWN')                                              AS store_province,
    COALESCE(loc.town, 'UNKNOWN')                                                  AS store_town,
    COALESCE(loc.postal_code, 'UNKNOWN')                                           AS store_postal_code,
    {{ bodega_json_scalar('_it.elem', '$.description') }}                          AS description_raw,
    trim(upper({{ bodega_json_scalar('_it.elem', '$.description') }}))             AS description_clean,
    CAST({{ bodega_json_scalar('_it.elem', '$.quantity') }} AS DOUBLE)             AS quantity,
    CASE
        WHEN CAST({{ bodega_json_scalar('_it.elem', '$.quantity') }} AS DOUBLE)
             != FLOOR(CAST({{ bodega_json_scalar('_it.elem', '$.quantity') }} AS DOUBLE))
        THEN 'KG' ELSE 'EA'
    END                                                                            AS unit,
    CAST({{ bodega_json_scalar('_it.elem', '$.unit_price') }} AS DOUBLE)           AS unit_price,
    CAST({{ bodega_json_scalar('_it.elem', '$.total') }} AS DOUBLE)                AS total_amount
FROM {{ source('bodega', 'raw_invoices') }} AS b
{{ bodega_explode_json('b.items_json') }}
LEFT JOIN store_location AS loc
    ON loc.address_key = {{ bodega_blank_to_null(bodega_address_key('b.store_address')) }}
