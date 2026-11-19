-- Dimension des stations exposée à Metabase.
-- Seules les stations rattachées à un département réel y figurent : la station de test
-- du flux (code postal 99999) en est écartée.
select
    id_station,
    adresse,
    ville,
    code_postal,
    code_departement,
    nom_departement,
    code_region,
    nom_region,
    latitude,
    longitude,
    type_route,
    a_automate_24_24,
    nb_services,
    fermeture_type,
    premiere_date_vue,
    derniere_date_vue,
    est_dans_dernier_fichier
from {{ ref('int_stations__derniere_version') }}
where nom_departement is not null
