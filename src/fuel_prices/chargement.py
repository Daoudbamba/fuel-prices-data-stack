"""Chargement idempotent d'un jour de données dans le schéma raw de l'entrepôt.

Rejouer une date donne toujours le même résultat : dans une seule transaction, on
supprime les lignes de cette date puis on les recharge avec COPY. Un verrou consultatif
par date empêche deux exécutions simultanées du même jour de se mélanger.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from dataclasses import astuple, fields
from datetime import date
from typing import Any

from fuel_prices.analyse import ContenuJour, Prix, Rupture, Station
from fuel_prices.telechargement import FichierTelecharge

DDL_RAW = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.stations (
    date_fichier     date        NOT NULL,
    id_station       text        NOT NULL,
    latitude         text,
    longitude        text,
    code_postal      text,
    type_route       text,
    adresse          text,
    ville            text,
    automate_24_24   text,
    services         jsonb       NOT NULL,
    fermeture_type   text,
    fermeture_debut  text,
    fermeture_fin    text,
    charge_le        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS stations_date_fichier_idx ON raw.stations (date_fichier);

CREATE TABLE IF NOT EXISTS raw.prix (
    date_fichier  date        NOT NULL,
    id_station    text        NOT NULL,
    id_carburant  text,
    carburant     text,
    maj           text,
    valeur        text,
    charge_le     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS prix_date_fichier_idx ON raw.prix (date_fichier);

CREATE TABLE IF NOT EXISTS raw.ruptures (
    date_fichier  date        NOT NULL,
    id_station    text        NOT NULL,
    id_carburant  text,
    carburant     text,
    debut         text,
    fin           text,
    type_rupture  text,
    charge_le     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ruptures_date_fichier_idx ON raw.ruptures (date_fichier);

-- Une ligne par jour chargé : traçabilité et source de la fraîcheur dbt.
CREATE TABLE IF NOT EXISTS raw.journal_ingestion (
    date_fichier   date        PRIMARY KEY,
    nom_fichier    text        NOT NULL,
    sha256         text        NOT NULL,
    taille_octets  bigint      NOT NULL,
    nb_stations    integer     NOT NULL,
    nb_prix        integer     NOT NULL,
    nb_ruptures    integer     NOT NULL,
    charge_le      timestamptz NOT NULL DEFAULT now()
);
"""

TABLES_DU_JOUR: tuple[tuple[str, type], ...] = (
    ("raw.stations", Station),
    ("raw.prix", Prix),
    ("raw.ruptures", Rupture),
)


def vers_csv(jour: date, lignes: Iterable[Any]) -> io.StringIO:
    """Sérialise des dataclasses en CSV pour COPY, la date du fichier en tête de ligne.

    None devient un champ vide non cité, que COPY lit comme NULL ; une chaîne vide
    n'existe pas ici (l'analyse la transforme déjà en None). Le module csv cite les
    virgules, guillemets et retours à la ligne présents dans les adresses.
    """
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, lineterminator="\n")
    for ligne in lignes:
        ecrivain.writerow([jour.isoformat(), *("" if v is None else v for v in astuple(ligne))])
    tampon.seek(0)
    return tampon


def colonnes(classe: type) -> Sequence[str]:
    return ["date_fichier", *(f.name for f in fields(classe))]


def charger_jour(
    connexion: Any,
    jour: date,
    contenu: ContenuJour,
    fichier: FichierTelecharge,
) -> dict[str, int]:
    """Remplace les données de ``jour`` dans raw et met à jour le journal d'ingestion.

    ``connexion`` est une connexion psycopg2. Tout se fait dans une transaction :
    en cas d'erreur, l'entrepôt garde l'état précédent de cette date.
    """
    lignes_par_table = {
        "raw.stations": contenu.stations,
        "raw.prix": contenu.prix,
        "raw.ruptures": contenu.ruptures,
    }
    with connexion:  # commit à la sortie, rollback sur exception
        with connexion.cursor() as curseur:
            curseur.execute(DDL_RAW)
            curseur.execute("SELECT pg_advisory_xact_lock(%s)", (int(f"{jour:%Y%m%d}"),))
            for table, classe in TABLES_DU_JOUR:
                curseur.execute(f"DELETE FROM {table} WHERE date_fichier = %s", (jour,))
                liste_colonnes = ", ".join(colonnes(classe))
                curseur.copy_expert(
                    f"COPY {table} ({liste_colonnes}) FROM STDIN WITH (FORMAT csv)",
                    vers_csv(jour, lignes_par_table[table]),
                )
            curseur.execute(
                """
                INSERT INTO raw.journal_ingestion
                    (date_fichier, nom_fichier, sha256, taille_octets,
                     nb_stations, nb_prix, nb_ruptures, charge_le)
                VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (date_fichier) DO UPDATE SET
                    nom_fichier = EXCLUDED.nom_fichier,
                    sha256 = EXCLUDED.sha256,
                    taille_octets = EXCLUDED.taille_octets,
                    nb_stations = EXCLUDED.nb_stations,
                    nb_prix = EXCLUDED.nb_prix,
                    nb_ruptures = EXCLUDED.nb_ruptures,
                    charge_le = EXCLUDED.charge_le
                """,
                (
                    jour,
                    fichier.chemin.name,
                    fichier.sha256,
                    fichier.taille_octets,
                    len(contenu.stations),
                    len(contenu.prix),
                    len(contenu.ruptures),
                ),
            )
    return {
        "stations": len(contenu.stations),
        "prix": len(contenu.prix),
        "ruptures": len(contenu.ruptures),
    }
