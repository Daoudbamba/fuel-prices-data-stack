{{ config(severity='warn') }}

-- Surveillance, sans blocage : prix récents du dernier jour qui s'écartent de plus du
-- seuil du projet de la médiane de leur département. Ce sont souvent des erreurs de
-- saisie des stations ; le tableau de bord les écarte, ce test les rend visibles.
select
    f.date_fichier,
    f.id_station,
    f.id_carburant,
    f.prix_litre,
    f.prix_median_departement,
    f.ecart_mediane_departement
from {{ ref('fct_prix_quotidiens') }} as f
where f.date_fichier = (select max(date_fichier) from {{ ref('fct_prix_quotidiens') }})
  and f.est_recent
  and f.est_atypique
