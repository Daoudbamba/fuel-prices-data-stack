{{ config(severity='warn') }}

-- Surveillance : part des stations du dernier fichier dont l'enseigne est connue.
-- Elle était de 92,8 % au 18/11/2026. Sous 85 %, l'extraction OSM est probablement
-- incomplète ou absente (premier démarrage : lancer le DAG enseignes_osm_hebdomadaire).
-- Avertissement seulement : une enseigne manquante ne fausse aucun prix.
with stations as (

    select enseigne
    from {{ ref('dim_stations') }}
    where est_dans_dernier_fichier

)

select
    count(*)                                                    as nb_stations,
    count(*) filter (where enseigne <> 'Inconnue')              as nb_avec_enseigne,
    round(count(*) filter (where enseigne <> 'Inconnue')::numeric / count(*), 3)
                                                                as couverture
from stations
having count(*) filter (where enseigne <> 'Inconnue')::numeric / nullif(count(*), 0) < 0.85
