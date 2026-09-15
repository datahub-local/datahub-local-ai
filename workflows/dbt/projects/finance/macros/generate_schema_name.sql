{#
  Use the configured schema verbatim (e.g. `silver.bodega`) instead of dbt's default
  `<target_schema>_<custom_schema>` concatenation. This lets each medallion layer target
  its own Iceberg catalog via the catalog-qualified schema.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
