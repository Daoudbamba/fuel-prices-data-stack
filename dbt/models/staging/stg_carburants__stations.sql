-- Une ligne par station et par fichier quotidien : types convertis, libellés lisibles.
with source as (

    select * from {{ source('carburants', 'stations') }}

)

select
    date_fichier,
    id_station::bigint                                   as id_station,
    code_postal,
    {{ code_departement('code_postal') }}                as code_departement,
    adresse,
    ville,
    -- Le flux donne les coordonnées en degrés multipliés par 100 000.
    latitude::numeric / 100000                           as latitude,
    longitude::numeric / 100000                          as longitude,
    case type_route when 'A' then 'autoroute' when 'R' then 'route' end
                                                         as type_route,
    coalesce(automate_24_24 = '1', false)                as a_automate_24_24,
    services,
    jsonb_array_length(services)                         as nb_services,
    case fermeture_type when 'D' then 'definitive' when 'T' then 'temporaire' end
                                                         as fermeture_type,
    fermeture_debut::timestamp                           as fermeture_debut,
    fermeture_fin::timestamp                             as fermeture_fin,
    charge_le
from source
