-- Une ligne par station, carburant et fichier quotidien.
--
-- Le flux contient de rares doublons exacts (38 lignes sur 34 jours d'octobre-novembre
-- 2026) : on ne garde qu'une ligne, la plus récemment mise à jour.
-- Les horodatages du flux sont en heure légale française, sans fuseau : on les
-- convertit en timestamptz.
with source as (

    select * from {{ source('carburants', 'prix') }}

),

types as (

    select
        date_fichier,
        id_station::bigint                                     as id_station,
        id_carburant::integer                                  as id_carburant,
        carburant                                              as code_carburant,
        (maj::timestamp at time zone 'Europe/Paris')           as maj,
        valeur::numeric(6, 3)                                  as prix_litre,
        charge_le
    from source

),

dedoublonne as (

    select
        *,
        row_number() over (
            partition by date_fichier, id_station, id_carburant
            order by maj desc
        ) as rang
    from types

)

select
    date_fichier,
    id_station,
    id_carburant,
    code_carburant,
    maj,
    prix_litre,
    charge_le
from dedoublonne
where rang = 1
