-- Une ligne par station : la marque OSM de la dernière extraction.
--
-- Certaines stations figurent sur plusieurs objets OSM (73 identifiants dans
-- l'extraction du 18/11/2026, dont 34 avec des marques différentes). Règle
-- déterministe : on préfère un objet qui porte une marque, puis le plus ancien
-- (plus petit identifiant OSM). Les cas de marques divergentes sont signalés.
with derniere_extraction as (

    select *
    from {{ source('osm', 'osm_enseignes') }}
    where date_extraction = (select max(date_extraction) from {{ source('osm', 'osm_enseignes') }})
      -- Les références sont numériques dans le flux officiel ; une saisie OSM
      -- fantaisiste ne doit pas faire échouer la conversion.
      and id_station ~ '^[0-9]+$'

),

classes as (

    select
        *,
        row_number() over (
            partition by id_station
            order by (marque is null), id_osm
        ) as rang
    from derniere_extraction

),

-- PostgreSQL n'accepte pas count(distinct) comme fonction de fenêtre.
marques_par_station as (

    select id_station, count(distinct marque) as nb_marques_distinctes
    from derniere_extraction
    group by id_station

)

select
    c.id_station::bigint            as id_station,
    c.date_extraction,
    c.type_osm,
    c.id_osm,
    c.marque                        as marque_osm,
    c.nom                           as nom_osm,
    c.operateur                     as operateur_osm,
    c.marque_wikidata,
    m.nb_marques_distinctes > 1     as est_marque_ambigue
from classes as c
inner join marques_par_station as m using (id_station)
where c.rang = 1
