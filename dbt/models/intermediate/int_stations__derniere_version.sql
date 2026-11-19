-- Une ligne par station : ses attributs dans le fichier le plus récent où elle figure,
-- avec sa période de présence dans le flux et sa localisation administrative.
with versions as (

    select
        *,
        row_number() over (partition by id_station order by date_fichier desc) as rang,
        min(date_fichier) over (partition by id_station)                        as premiere_date_vue,
        max(date_fichier) over (partition by id_station)                        as derniere_date_vue
    from {{ ref('stg_carburants__stations') }}

),

dernier_fichier as (

    select max(date_fichier) as date_fichier from {{ ref('stg_carburants__journal_ingestion') }}

)

select
    v.id_station,
    v.adresse,
    v.ville,
    v.code_postal,
    v.code_departement,
    d.nom_departement,
    d.code_region,
    r.nom_region,
    v.latitude,
    v.longitude,
    v.type_route,
    v.a_automate_24_24,
    v.nb_services,
    v.services,
    v.fermeture_type,
    v.premiere_date_vue,
    v.derniere_date_vue,
    v.derniere_date_vue = f.date_fichier as est_dans_dernier_fichier,
    e.marque_osm,
    -- Station absente d'OpenStreetMap : enseigne inconnue.
    coalesce(e.enseigne, 'Inconnue')                     as enseigne,
    coalesce(e.type_enseigne, 'inconnu')                 as type_enseigne,
    coalesce(e.est_marque_ambigue, false)                as est_marque_ambigue
from versions as v
cross join dernier_fichier as f
left join {{ ref('departements') }} as d on d.code_departement = v.code_departement
left join {{ ref('regions') }} as r on r.code_region = d.code_region
left join {{ ref('int_stations__enseignes') }} as e on e.id_station = v.id_station
where v.rang = 1
