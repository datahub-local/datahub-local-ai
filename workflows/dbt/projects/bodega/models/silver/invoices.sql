{#
  Location is denormalised from `stores` rather than joined at query time: the semantic
  compiler emits one FROM and every dimension must be a bare column on the metric's own
  model, so a location filter only works if these columns live here. LEFT join with an
  UNKNOWN sentinel, so a store whose address did not parse keeps its spend in the total.

  The join is on the normalised address, not `store_vat_id`: that column is the operating
  company's VAT, so a chain shares one across every shop and joining on it would give
  every branch the same town.
#}
WITH store_location AS (
    SELECT address_key, store_id, store_name, province, town, postal_code
    FROM {{ ref('stores') }}
)

SELECT
    b.invoice_number,
    {{ bodega_parse_dt('b.invoice_date') }}                             AS invoice_datetime,
    CAST({{ bodega_parse_dt('b.invoice_date') }} AS DATE)               AS invoice_date,
    year({{ bodega_parse_dt('b.invoice_date') }})                       AS invoice_year,
    month({{ bodega_parse_dt('b.invoice_date') }})                      AS invoice_month,
    week({{ bodega_parse_dt('b.invoice_date') }})                       AS invoice_week,
    b.operator_id,
    b.store_vat_id,
    trim(upper(b.store_name))                                           AS company_name,
    loc.store_id,
    COALESCE(loc.store_name, 'UNKNOWN')                                 AS store_name,
    COALESCE(loc.province, 'UNKNOWN')                                   AS store_province,
    COALESCE(loc.town, 'UNKNOWN')                                       AS store_town,
    COALESCE(loc.postal_code, 'UNKNOWN')                                AS store_postal_code,
    b.total_amount,
    {{ bodega_json_sum('b.taxes_json', 'tax') }}                        AS total_tax_amount,
    {{ bodega_json_sum('b.taxes_json', 'base') }}                       AS total_base_amount,
    b.payment_method,
    b.card_type,
    b.card_number_masked,
    b.supermarket,
    {{ bodega_json_len('b.items_json') }}                               AS item_count,
    b._ingested_at
FROM {{ source('bodega', 'raw_invoices') }} AS b
LEFT JOIN store_location AS loc
    ON loc.address_key = {{ bodega_blank_to_null(bodega_address_key('b.store_address')) }}
