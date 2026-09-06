{#
  Cross-dialect helpers for the bodega silver models. homelab runs on Trino, local on
  DuckDB; the two engines differ in timestamp parsing, JSON extraction, and how a JSON
  array is exploded with positional ordinality. Each helper dispatches on the adapter so
  the silver models share one body across both engines
  (same pattern as pi/macros/generate_samples.sql).
#}

{# Parse the ISO-8601 invoice timestamp string into a native timestamp. #}
{% macro bodega_parse_dt(col) -%}
    {{ return(adapter.dispatch('bodega_parse_dt', 'bodega')(col)) }}
{%- endmacro %}
{% macro trino__bodega_parse_dt(col) -%}
    date_parse({{ col }}, '%Y-%m-%dT%H:%i:%s')
{%- endmacro %}
{% macro duckdb__bodega_parse_dt(col) -%}
    strptime({{ col }}, '%Y-%m-%dT%H:%M:%S')
{%- endmacro %}

{# Extract a scalar string from a JSON element at the given path (e.g. '$.description'). #}
{% macro bodega_json_scalar(elem, path) -%}
    {{ return(adapter.dispatch('bodega_json_scalar', 'bodega')(elem, path)) }}
{%- endmacro %}
{% macro trino__bodega_json_scalar(elem, path) -%}
    json_extract_scalar({{ elem }}, '{{ path }}')
{%- endmacro %}
{% macro duckdb__bodega_json_scalar(elem, path) -%}
    json_extract_string({{ elem }}, '{{ path }}')
{%- endmacro %}

{# Number of elements in a JSON-array string column. #}
{% macro bodega_json_len(col) -%}
    {{ return(adapter.dispatch('bodega_json_len', 'bodega')(col)) }}
{%- endmacro %}
{% macro trino__bodega_json_len(col) -%}
    CARDINALITY(CAST(json_parse({{ col }}) AS ARRAY(JSON)))
{%- endmacro %}
{% macro duckdb__bodega_json_len(col) -%}
    json_array_length(CAST({{ col }} AS JSON))
{%- endmacro %}

{# SUM a numeric field (e.g. 'tax') across every element of a JSON-array string column. #}
{% macro bodega_json_sum(col, field) -%}
    {{ return(adapter.dispatch('bodega_json_sum', 'bodega')(col, field)) }}
{%- endmacro %}
{% macro trino__bodega_json_sum(col, field) -%}
    (
        SELECT SUM(CAST(json_extract_scalar(e, '$.{{ field }}') AS DOUBLE))
        FROM UNNEST(CAST(json_parse({{ col }}) AS ARRAY(JSON))) AS u(e)
    )
{%- endmacro %}
{% macro duckdb__bodega_json_sum(col, field) -%}
    (
        SELECT SUM(CAST(json_extract_string(e, '$.{{ field }}') AS DOUBLE))
        FROM UNNEST(json_extract({{ col }}, '$[*]')) AS u(e)
    )
{%- endmacro %}

{# FROM-clause fragment that explodes a JSON-array string column into one row per element,
   exposing `_it.elem` (the JSON element) and `_it.pos` (1-based position). #}
{% macro bodega_explode_json(col) -%}
    {{ return(adapter.dispatch('bodega_explode_json', 'bodega')(col)) }}
{%- endmacro %}
{% macro trino__bodega_explode_json(col) -%}
    CROSS JOIN UNNEST(CAST(json_parse({{ col }}) AS ARRAY(JSON))) WITH ORDINALITY AS _it(elem, pos)
{%- endmacro %}
{% macro duckdb__bodega_explode_json(col) -%}
    CROSS JOIN (
        SELECT json_extract({{ col }}, '$[' || g.i || ']') AS elem, g.i + 1 AS pos
        FROM range(CAST(json_array_length(CAST({{ col }} AS JSON)) AS BIGINT)) AS g(i)
    ) AS _it
{%- endmacro %}

{# Postal code, province code and town, parsed out of the free-text store address.
   The parser emits `<street>, <number>, <5-digit CP> <TOWN>`, so the CP is anchored to
   the tail: a 5-digit house number earlier in the string would otherwise win. The
   01..52 bound on the first two digits (the INE CPRO) is what keeps a phone fragment
   from matching. Group 1+2 is the CP, group 3 the town remainder.
   Trino returns NULL for no match and DuckDB returns '', so every caller must treat
   both as unparsed - `bodega_blank_to_null` normalises them. #}
{% macro bodega_address_part(col, group) -%}
    {{ return(adapter.dispatch('bodega_address_part', 'bodega')(col, group)) }}
{%- endmacro %}
{% macro trino__bodega_address_part(col, group) -%}
    regexp_extract({{ col }}, '.*(0[1-9]|[1-4][0-9]|5[0-2])([0-9]{3})[ ,]*([^0-9,]*)', {{ group }})
{%- endmacro %}
{% macro duckdb__bodega_address_part(col, group) -%}
    regexp_extract({{ col }}, '.*(0[1-9]|[1-4][0-9]|5[0-2])([0-9]{3})[ ,]*([^0-9,]*)', {{ group }})
{%- endmacro %}

{# NULLIF over trim, so DuckDB's '' non-match and Trino's NULL both become NULL. #}
{% macro bodega_blank_to_null(expr) -%}
    NULLIF(trim({{ expr }}), '')
{%- endmacro %}

{# Uppercase and strip diacritics. The filter target for a town name: the warehouse
   holds the accented form (DENIA arrives as the accented spelling) while receipts and
   questions use both, and the semantic layer's near-miss suggester is skipped for
   `contains`, so a wrong-accent filter would silently return zero rows. #}
{% macro bodega_unaccent_upper(expr) -%}
    {{ return(adapter.dispatch('bodega_unaccent_upper', 'bodega')(expr)) }}
{%- endmacro %}
{% macro trino__bodega_unaccent_upper(expr) -%}
    upper(regexp_replace(normalize({{ expr }}, NFD), '\p{Mn}', ''))
{%- endmacro %}
{% macro duckdb__bodega_unaccent_upper(expr) -%}
    upper(strip_accents({{ expr }}))
{%- endmacro %}

{# The INE province code list (CPRO): 52 rows, code -> name, as a joinable relation.
   Inlined rather than seeded because dbt's Jinja cannot read a file and a seed would
   add a materialisation and a DAG step for 52 static rows. Codes are the join key and
   are stable; names are display only. Accented names are the official spelling - join
   on the code, never on the name. #}
{% macro bodega_provinces() -%}
    (
        SELECT * FROM (
            VALUES
                ('01', 'Araba/Álava'),        ('02', 'Albacete'),
                ('03', 'Alicante/Alacant'),   ('04', 'Almería'),
                ('05', 'Ávila'),              ('06', 'Badajoz'),
                ('07', 'Illes Balears'),      ('08', 'Barcelona'),
                ('09', 'Burgos'),             ('10', 'Cáceres'),
                ('11', 'Cádiz'),              ('12', 'Castellón/Castelló'),
                ('13', 'Ciudad Real'),        ('14', 'Córdoba'),
                ('15', 'A Coruña'),           ('16', 'Cuenca'),
                ('17', 'Girona'),             ('18', 'Granada'),
                ('19', 'Guadalajara'),        ('20', 'Gipuzkoa'),
                ('21', 'Huelva'),             ('22', 'Huesca'),
                ('23', 'Jaén'),               ('24', 'León'),
                ('25', 'Lleida'),             ('26', 'La Rioja'),
                ('27', 'Lugo'),               ('28', 'Madrid'),
                ('29', 'Málaga'),             ('30', 'Murcia'),
                ('31', 'Navarra'),            ('32', 'Ourense'),
                ('33', 'Asturias'),           ('34', 'Palencia'),
                ('35', 'Las Palmas'),         ('36', 'Pontevedra'),
                ('37', 'Salamanca'),          ('38', 'Santa Cruz de Tenerife'),
                ('39', 'Cantabria'),          ('40', 'Segovia'),
                ('41', 'Sevilla'),            ('42', 'Soria'),
                ('43', 'Tarragona'),          ('44', 'Teruel'),
                ('45', 'Toledo'),             ('46', 'Valencia/València'),
                ('47', 'Valladolid'),         ('48', 'Bizkaia'),
                ('49', 'Zamora'),             ('50', 'Zaragoza'),
                ('51', 'Ceuta'),              ('52', 'Melilla')
        ) AS _p(province_code, province_name)
    )
{%- endmacro %}
