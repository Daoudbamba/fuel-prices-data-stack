-- Prix par région, carburant et jour, plus une ligne « France » par carburant et jour.
-- Seuls les prix récents et non atypiques entrent dans les agrégats.
with prix as (

    select
        f.date_fichier,
        f.id_carburant,
        f.prix_litre,
        f.id_station,
        s.code_region,
        s.nom_region
    from {{ ref('fct_prix_quotidiens') }} as f
    inner join {{ ref('dim_stations') }} as s on s.id_station = f.id_station
    where f.est_recent
      and not f.est_atypique

),

agregats as (

    select
        date_fichier,
        id_carburant,
        coalesce(code_region, 'FR')                                     as code_region,
        coalesce(nom_region, 'France')                                  as nom_region,
        round(avg(prix_litre), 3)                                       as prix_moyen,
        round(percentile_cont(0.5) within group (order by prix_litre)::numeric, 3)
                                                                        as prix_median,
        min(prix_litre)                                                 as prix_min,
        max(prix_litre)                                                 as prix_max,
        count(distinct id_station)                                      as nb_stations
    from prix
    group by grouping sets (
        (date_fichier, id_carburant, code_region, nom_region),
        (date_fichier, id_carburant)
    )

)

select
    a.date_fichier,
    a.code_region,
    a.nom_region,
    a.code_region = 'FR' as est_national,
    c.code_carburant,
    c.libelle as libelle_carburant,
    a.prix_moyen,
    a.prix_median,
    a.prix_min,
    a.prix_max,
    a.nb_stations
from agregats as a
inner join {{ ref('dim_carburants') }} as c on c.id_carburant = a.id_carburant
