{#
  One row per store VAT ID. The raw invoices can carry formatting variants of the
  descriptive fields (name casing, address, phone) for the same store, so those are
  taken from the most recent invoice instead of being grouped on.

  Location is parsed out of `address` rather than joined from a dataset: the receipt
  parser already prints a 5-digit postal code whose first two digits are the INE
  province code. Every location column falls back to the literal UNKNOWN so an
  unparseable address keeps its spend in a grouped total instead of vanishing.
#}
WITH ranked AS (
    SELECT
        store_vat_id,
        store_name,
        store_address,
        store_phone,
        supermarket,
        CAST({{ bodega_parse_dt('invoice_date') }} AS DATE)                     AS invoice_date,
        ROW_NUMBER() OVER (
            PARTITION BY store_vat_id
            ORDER BY {{ bodega_parse_dt('invoice_date') }} DESC, invoice_number DESC
        )                                                                       AS rn
    FROM {{ source('bodega', 'raw_invoices') }}
),

parsed AS (
    SELECT
        ranked.*,
        {{ bodega_blank_to_null(bodega_address_part('ranked.store_address', 1)) }} AS cp_province,
        {{ bodega_blank_to_null(bodega_address_part('ranked.store_address', 2)) }} AS cp_rest,
        {{ bodega_blank_to_null(bodega_address_part('ranked.store_address', 3)) }} AS town_parsed
    FROM ranked
)

SELECT
    parsed.store_vat_id                                                         AS store_id,
    trim(upper(parsed.store_name))                                              AS name,
    parsed.store_vat_id                                                         AS vat_id,
    parsed.store_address                                                        AS address,
    parsed.store_phone                                                          AS phone,
    parsed.supermarket,
    COALESCE(parsed.cp_province || parsed.cp_rest, 'UNKNOWN')                   AS postal_code,
    COALESCE(parsed.cp_province, 'UNKNOWN')                                     AS province_code,
    COALESCE(prov.province_name, 'UNKNOWN')                                     AS province,
    COALESCE(parsed.town_parsed, 'UNKNOWN')                                     AS town_raw,
    COALESCE({{ bodega_unaccent_upper('parsed.town_parsed') }}, 'UNKNOWN')      AS town,
    seen.first_seen_date,
    seen.last_seen_date
FROM parsed
JOIN (
    SELECT
        store_vat_id,
        MIN(invoice_date)                                                       AS first_seen_date,
        MAX(invoice_date)                                                       AS last_seen_date
    FROM ranked
    GROUP BY store_vat_id
) AS seen ON seen.store_vat_id = parsed.store_vat_id
LEFT JOIN {{ bodega_provinces() }} AS prov ON prov.province_code = parsed.cp_province
WHERE parsed.rn = 1
