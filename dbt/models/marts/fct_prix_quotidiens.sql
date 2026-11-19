{#
    Table de faits : un prix par station, carburant et jour de fichier.

    Incrémentale : à chaque exécution, seules les dates chargées (ou rechargées) depuis
    la dernière construction sont recalculées. La stratégie delete+insert sur
    date_fichier remplace une date entière : rejouer un jour dans Airflow puis lancer
    dbt corrige la table sans doublon.
#}
{{
    config(
        materialized='incremental',
        incremental_strategy='delete+insert',
        unique_key='date_fichier',
        indexes=[
            {'columns': ['date_fichier']},
            {'columns': ['id_station']},
        ],
    )
}}

-- Le journal n'est lu qu'en mode incrémental : on déclare la dépendance pour le graphe.
-- depends_on: {{ ref('stg_carburants__journal_ingestion') }}

with prix as (

    select * from {{ ref('int_prix__qualifies') }}
    {% if is_incremental() %}
    where date_fichier in (
        select date_fichier
        from {{ ref('stg_carburants__journal_ingestion') }}
        where charge_le > (select coalesce(max(charge_le), '-infinity') from {{ this }})
    )
    {% endif %}

)

select
    p.date_fichier,
    p.id_station,
    p.id_carburant,
    p.prix_litre,
    p.maj,
    p.age_prix_jours,
    p.est_recent,
    p.prix_median_departement,
    p.ecart_mediane_departement,
    p.est_atypique,
    p.charge_le
from prix as p
-- Garde l'intégrité référentielle avec la dimension (station de test exclue).
inner join {{ ref('dim_stations') }} as s on s.id_station = p.id_station
