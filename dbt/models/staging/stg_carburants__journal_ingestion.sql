select
    date_fichier,
    nom_fichier,
    sha256,
    taille_octets,
    nb_stations,
    nb_prix,
    nb_ruptures,
    charge_le
from {{ source('carburants', 'journal_ingestion') }}
