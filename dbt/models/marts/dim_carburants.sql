select
    id_carburant,
    code_carburant,
    libelle,
    famille,
    prix_min_plausible,
    prix_max_plausible
from {{ ref('carburants') }}
