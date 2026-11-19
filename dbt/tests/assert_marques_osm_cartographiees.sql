{{ config(severity='warn') }}

-- Maintenance du référentiel : marques OSM portées par au moins 5 stations et absentes
-- de seeds/correspondance_enseignes.csv. Elles tombent dans « Autre » ; si une nouvelle
-- graphie d'une grande enseigne apparaît dans OSM, ce test le signale.
select
    marque_osm,
    count(*) as nb_stations
from {{ ref('stg_osm__enseignes') }}
where marque_osm is not null
  and marque_osm not in (select marque_osm from {{ ref('correspondance_enseignes') }})
group by marque_osm
having count(*) >= 5
order by nb_stations desc
