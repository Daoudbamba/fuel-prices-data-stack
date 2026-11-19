-- Classement des stations par prix, sur le dernier fichier chargé : rang national et
-- rang dans le département, par carburant. Prix récents et non atypiques uniquement.
with dernier_jour as (

    select max(date_fichier) as date_fichier from {{ ref('fct_prix_quotidiens') }}

),

prix as (

    select f.*
    from {{ ref('fct_prix_quotidiens') }} as f
    inner join dernier_jour as d on d.date_fichier = f.date_fichier
    where f.est_recent
      and not f.est_atypique

)

select
    p.date_fichier,
    c.code_carburant,
    p.id_station,
    s.adresse,
    s.ville,
    s.enseigne,
    s.code_postal,
    s.nom_departement,
    s.nom_region,
    s.type_route,
    s.latitude,
    s.longitude,
    p.prix_litre,
    p.maj,
    p.prix_median_departement,
    rank() over (partition by p.id_carburant order by p.prix_litre)    as rang_national,
    rank() over (
        partition by p.id_carburant, s.code_departement order by p.prix_litre
    )                                                                   as rang_departement
from prix as p
inner join {{ ref('dim_stations') }} as s on s.id_station = p.id_station
inner join {{ ref('dim_carburants') }} as c on c.id_carburant = p.id_carburant
