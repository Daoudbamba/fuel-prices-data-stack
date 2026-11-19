"""Charge le jeu de données réduit de tests/donnees dans une base PostgreSQL de test.

Utilisé par la CI avant « dbt build » : le code d'ingestion de production charge deux
vrais fichiers quotidiens réduits à 250 stations (voir scripts/creer_echantillon_ci.py).

Les enseignes, elles, sont SYNTHÉTIQUES : on ne versionne pas d'extrait OpenStreetMap.
Des marques du référentiel sont attribuées tour à tour aux stations de l'échantillon,
avec quelques cas particuliers (marque absente, marque hors référentiel, station portée
par deux objets OSM) pour exercer les modèles et les tests dbt.

Connexion : variables ENTREPOT_HOST, ENTREPOT_PORT, ENTREPOT_DB, ENTREPOT_USER,
ENTREPOT_PASSWORD.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from itertools import cycle
from pathlib import Path

from fuel_prices.analyse import analyser_zip
from fuel_prices.ingestion import charger_fichier, connexion_depuis_environnement
from fuel_prices.osm import EnseigneOsm
from fuel_prices.osm import charger as charger_osm
from fuel_prices.telechargement import FichierTelecharge

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "tests" / "donnees"
MARQUES_SYNTHETIQUES = [
    "Intermarché",
    "TotalEnergies",
    "Carrefour Market",
    "E.Leclerc",
    "Esso Express",
    "Total Access",
    "Super U",
    "Avia",
    None,  # station présente dans OSM sans marque
    "Marque locale",  # absente du référentiel : devient « Autre »
]


def date_du_fichier(chemin: Path) -> date:
    trouve = re.search(r"(\d{8})", chemin.name)
    if not trouve:
        raise ValueError(f"Date introuvable dans {chemin.name}")
    return date.fromisoformat(f"{trouve[1][:4]}-{trouve[1][4:6]}-{trouve[1][6:]}")


def main() -> None:
    fichiers = sorted(DONNEES.glob("PrixCarburants_quotidien_*.zip"))
    if not fichiers:
        raise SystemExit(f"Aucun fichier dans {DONNEES}")
    connexion = connexion_depuis_environnement()
    try:
        for chemin in fichiers:
            contenu = chemin.read_bytes()
            fichier = FichierTelecharge(
                chemin, hashlib.sha256(contenu).hexdigest(), len(contenu), deja_present=True
            )
            comptes = charger_fichier(date_du_fichier(chemin), connexion, fichier)
            print(f"{chemin.name} : {comptes}")

        stations = sorted(s.id_station for s in analyser_zip(fichiers[-1]).stations)
        marques = cycle(MARQUES_SYNTHETIQUES)
        lignes = [
            EnseigneOsm(identifiant, "node", 1000 + rang, next(marques), None, None, None)
            for rang, identifiant in enumerate(stations)
        ]
        # Une station portée par deux objets OSM aux marques différentes.
        lignes.append(EnseigneOsm(stations[0], "way", 999, "Shell", None, None, None))
        nb = charger_osm(connexion, date_du_fichier(fichiers[-1]), lignes)
        print(f"Enseignes synthétiques : {nb} lignes")
    finally:
        connexion.close()


if __name__ == "__main__":
    main()
