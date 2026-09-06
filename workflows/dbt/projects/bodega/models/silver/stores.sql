{#
  One row per physical shop. The key is a hash of the normalised address, not the VAT:
  `store_vat_id` is the operating company's VAT, so a chain prints the same one on every
  receipt and partitioning on it collapses every shop of that chain into a single row,
  handing invoices the address of whichever receipt happened to be latest.

  Receipts carry the same shop under different street-type abbreviations, so the raw
  address is not a key either - `bodega_address_key` normalises it and `store_id` is its
  hash. `store_label` is the readable form of the same identity, for a reader who needs
  to tell shops apart without decoding a hash.

  Descriptive fields are taken from the most recent invoice for the shop rather than
  grouped on, since the parser emits casing and punctuation variants.

  Location is parsed out of `address` rather than joined from a dataset: the receipt
  parser already prints a 5-digit postal code whose first two digits are the INE
  province code. Every location column falls back to the literal UNKNOWN so an
  unparseable address keeps its spend in a grouped total instead of vanishing.
#}
WITH keyed AS (
    SELECT
        store_vat_id,
        store_name,
        store_address,
        store_phone,
        supermarket,
        invoice_number,
        {{ bodega_blank_to_null(bodega_address_key('store_address')) }}          AS address_key,
        CAST({{ bodega_parse_dt('invoice_date') }} AS DATE)                      AS invoice_date
    FROM {{ source('bodega', 'raw_invoices') }}
),

{#  An unparseable address has no shop identity to hash, so it falls back to the VAT.
    Every such receipt for one company lands on a single UNKNOWN-address row rather than
    one row per receipt, and its spend still totals. #}
identified AS (
    SELECT
        keyed.*,
        COALESCE(address_key, 'VAT:' || store_vat_id)                            AS identity_key
    FROM keyed
),

ranked AS (
    SELECT
        identified.*,
        ROW_NUMBER() OVER (
            PARTITION BY identity_key
            ORDER BY invoice_date DESC, invoice_number DESC
        )                                                                        AS rn
    FROM identified
),

parsed AS (
    SELECT
        ranked.*,
        {{ bodega_blank_to_null(bodega_address_part('ranked.store_address', 1)) }} AS cp_province,
        {{ bodega_blank_to_null(bodega_address_part('ranked.store_address', 2)) }} AS cp_rest,
        {{ bodega_blank_to_null(bodega_address_part('ranked.store_address', 3)) }} AS town_parsed,
        {{ bodega_blank_to_null(bodega_street_key('ranked.address_key')) }}        AS street_key
    FROM ranked
)

SELECT
    {{ bodega_md5_hex('parsed.identity_key') }}                                 AS store_id,
    trim(upper(parsed.store_name))                                              AS name,
    parsed.store_vat_id                                                         AS vat_id,
    parsed.store_address                                                        AS address,
    parsed.address_key,
    parsed.store_phone                                                          AS phone,
    parsed.supermarket,
    COALESCE(parsed.cp_province || parsed.cp_rest, 'UNKNOWN')                   AS postal_code,
    COALESCE(parsed.cp_province, 'UNKNOWN')                                     AS province_code,
    COALESCE(prov.province_name, 'UNKNOWN')                                     AS province,
    COALESCE(parsed.town_parsed, 'UNKNOWN')                                     AS town_raw,
    COALESCE({{ bodega_unaccent_upper('parsed.town_parsed') }}, 'UNKNOWN')      AS town,
    trim(upper(parsed.store_name))
        || ' - ' || COALESCE(parsed.street_key, 'ADDRESS UNPARSED')
        || COALESCE(
               ', ' || {{ bodega_unaccent_upper('parsed.town_parsed') }}
                    || ' (' || parsed.cp_province || parsed.cp_rest || ')',
               '')                                                              AS store_label,
    seen.first_seen_date,
    seen.last_seen_date
FROM parsed
JOIN (
    SELECT
        identity_key,
        MIN(invoice_date)                                                       AS first_seen_date,
        MAX(invoice_date)                                                       AS last_seen_date
    FROM identified
    GROUP BY identity_key
) AS seen ON seen.identity_key = parsed.identity_key
LEFT JOIN {{ bodega_provinces() }} AS prov ON prov.province_code = parsed.cp_province
WHERE parsed.rn = 1
