{#
    Code département déduit du code postal.
    - Métropole : les deux premiers chiffres.
    - Corse : les codes postaux commencent par 20 ; 200xx et 201xx sont en
      Corse-du-Sud (2A), les autres (202xx, 206xx) en Haute-Corse (2B).
    - Outre-mer : les trois premiers chiffres (971 à 976).
    Un code postal mal formé donne NULL : la station sort des marts et le test
    de relation vers le référentiel des départements le signale.
#}
{% macro code_departement(code_postal) -%}
    case
        when {{ code_postal }} !~ '^[0-9]{5}$' then null
        when left({{ code_postal }}, 2) = '20'
            then case when left({{ code_postal }}, 3) in ('200', '201') then '2A' else '2B' end
        when left({{ code_postal }}, 2) = '97' then left({{ code_postal }}, 3)
        else left({{ code_postal }}, 2)
    end
{%- endmacro %}
