-- Test métier : un fichier quotidien complet décrit environ 9 950 stations
-- (9 943 à 9 955 entre le 15/10 et le 17/11/2026). En dessous du seuil (9 000 par
-- défaut), le fichier est tronqué ou l'analyse incomplète : on bloque la suite plutôt
-- que de publier des moyennes calculées sur une France partielle.
-- La CI, qui travaille sur un extrait de 250 stations, abaisse le seuil par variable.
select
    date_fichier,
    nb_stations
from {{ ref('stg_carburants__journal_ingestion') }}
where nb_stations < {{ var('nb_stations_min_par_jour') }}
