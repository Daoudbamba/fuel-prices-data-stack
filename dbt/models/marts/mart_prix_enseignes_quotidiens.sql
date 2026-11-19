-- Prix par enseigne (et par type d'enseigne), carburant et jour.
-- Prix récents et non atypiques uniquement. Une moyenne sur une poignée de stations
-- n'a pas de sens : on ne publie un agrégat qu'à partir de 10 stations.
{% set nb_stations_min = 10 %}

with prix as (

    select
        f.date_fichier,
        f.id_carburant,
        f.id_station,
        f.prix_litre,
        s.enseigne,
        s.type_enseigne
    from {{ ref('fct_prix_quotidiens') }} as f
    inner join {{ ref('dim_stations') }} as s on s.id_station = f.id_station
    where f.est_recent
      and not f.est_atypique

),

agregats as (

    select
        date_fichier,
        id_carburant,
        case when grouping(enseigne) = 0 then 'enseigne' else 'type_enseigne' end
                                                                        as niveau,
        enseigne,
        type_enseigne,
        round(avg(prix_litre), 3)                                       as prix_moyen,
        round(percentile_cont(0.5) within group (order by prix_litre)::numeric, 3)
                                                                        as prix_median,
        count(distinct id_station)                                      as nb_stations
    from prix
    group by grouping sets (
        (date_fichier, id_carburant, enseigne, type_enseigne),
        (date_fichier, id_carburant, type_enseigne)
    )
    having count(distinct id_station) >= {{ nb_stations_min }}

)

select
    a.date_fichier,
    a.niveau,
    a.enseigne,
    a.type_enseigne,
    c.code_carburant,
    c.libelle as libelle_carburant,
    a.prix_moyen,
    a.prix_median,
    a.nb_stations
from agregats as a
inner join {{ ref('dim_carburants') }} as c on c.id_carburant = a.id_carburant
