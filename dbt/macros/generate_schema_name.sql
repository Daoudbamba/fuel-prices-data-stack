{#
    Par défaut, dbt préfixe les schémas personnalisés par celui du profil
    (public_staging, public_marts...). Ici chaque couche a son schéma propre et stable :
    staging, intermediate, marts, referentiel, audit. Metabase n'a accès qu'à marts.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
