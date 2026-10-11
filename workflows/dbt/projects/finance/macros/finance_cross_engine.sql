{#
  Cross-dialect helpers for the finance silver models. homelab runs on Trino, local
  on DuckDB; they differ in whitespace-regex flags and in parsing an ISO-8601 timestamp
  with an offset into a DATE. Each helper dispatches on the adapter so the silver models
  share one body across both engines (same pattern as bodega/macros/cross_engine.sql).
#}

{# The enrich join key: uppercase, trimmed, whitespace runs collapsed to one space.
   DuckDB's regexp_replace replaces only the first match unless 'g' is passed, while
   Trino always replaces every match - unsplit, the same payee would key differently
   per engine and the categorisation join would silently miss. #}
{% macro finance_clean_key(expr) -%}
    {{ return(adapter.dispatch('finance_clean_key', 'finance')(expr)) }}
{%- endmacro %}
{% macro trino__finance_clean_key(expr) -%}
    upper(trim(regexp_replace({{ expr }}, '\s+', ' ')))
{%- endmacro %}
{% macro duckdb__finance_clean_key(expr) -%}
    upper(trim(regexp_replace({{ expr }}, '\s+', ' ', 'g')))
{%- endmacro %}

{# Is this stable_id a booking-date-scoped positional ordinal? Same shape rule as
   the ingest adapter's `_POSITIONAL_REFERENCE` (something like `2026-09-28.9` is
   "the tenth transaction booked that day", not an identity). An ordinal and the
   hash minted for the same payment are two rows for one transaction, so a
   consumer of silver must be able to tell them apart; the dedup in
   `silver/transactions.sql` ranks on this. `regexp_like`/`regexp_matches` are the
   Trino/DuckDB spellings of the same RE2 class. #}
{% macro finance_is_positional_id(expr) -%}
    {{ return(adapter.dispatch('finance_is_positional_id', 'finance')(expr)) }}
{%- endmacro %}
{% macro trino__finance_is_positional_id(expr) -%}
    regexp_like({{ expr }}, '^\d{4}-\d{2}-\d{2}\.\d+$')
{%- endmacro %}
{% macro duckdb__finance_is_positional_id(expr) -%}
    regexp_matches({{ expr }}, '^\d{4}-\d{2}-\d{2}\.\d+$')
{%- endmacro %}

{# Parse the loader's ISO-8601 `_ingested_at` (with offset) into a DATE. Trino's
   from_iso8601_timestamp understands the offset; DuckDB needs an explicit TIMESTAMPTZ
   cast first. #}
{% macro finance_iso_date(expr) -%}
    {{ return(adapter.dispatch('finance_iso_date', 'finance')(expr)) }}
{%- endmacro %}
{% macro trino__finance_iso_date(expr) -%}
    CAST(from_iso8601_timestamp({{ expr }}) AS DATE)
{%- endmacro %}
{% macro duckdb__finance_iso_date(expr) -%}
    CAST(CAST({{ expr }} AS TIMESTAMPTZ) AS DATE)
{%- endmacro %}
