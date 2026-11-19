-- Test métier : un fichier quotidien complet décrit environ 9 950 stations
-- (9 943 à 9 955 entre le 15/10 et le 17/11/2026). Moins de 9 000 signale un
-- fichier tronqué ou une analyse incomplète : on bloque la suite plutôt que de
-- publier des moyennes calculées sur une France partielle.
select
    date_fichier,
    nb_stations
from {{ ref('stg_carburants__journal_ingestion') }}
where nb_stations < 9000
