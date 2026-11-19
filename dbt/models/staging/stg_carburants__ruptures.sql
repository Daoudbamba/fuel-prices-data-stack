-- Une ligne par rupture déclarée, par station, carburant et fichier quotidien.
select
    date_fichier,
    id_station::bigint                                         as id_station,
    id_carburant::integer                                      as id_carburant,
    carburant                                                  as code_carburant,
    (debut::timestamp at time zone 'Europe/Paris')             as debut,
    (fin::timestamp at time zone 'Europe/Paris')               as fin,
    -- Environ 4 % des ruptures n'ont pas de type dans le flux.
    coalesce(type_rupture, 'non_precise')                      as type_rupture
from {{ source('carburants', 'ruptures') }}
