"""Construit le jeu de données réduit utilisé par la CI, à partir de vrais fichiers quotidiens.

On garde les mêmes stations dans chaque fichier : une sur 40 (tri par identifiant, donc
réparties sur tout le territoire), plus la station de test du flux (99999001), pour que
dbt rencontre les mêmes cas qu'en production. Les points de vente sont recopiés tels
quels : structure, encodage ISO-8859-1 et anomalies d'origine compris.

Données : prix-carburants.gouv.fr, Licence Ouverte / Etalab.

Usage :
    python scripts/creer_echantillon_ci.py ZIP_QUOTIDIEN [ZIP_QUOTIDIEN ...]
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

RACINE = Path(__file__).resolve().parent.parent
DESTINATION = RACINE / "tests" / "donnees"
PAS = 40
STATIONS_TOUJOURS_GARDEES = {"99999001"}


def stations_retenues(points_de_vente: list[ET.Element]) -> set[str]:
    identifiants = sorted(p.get("id") for p in points_de_vente)
    return set(identifiants[::PAS]) | STATIONS_TOUJOURS_GARDEES


def main(chemins: list[Path]) -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    retenues: set[str] | None = None
    for chemin in chemins:
        with zipfile.ZipFile(chemin) as archive:
            nom_xml = archive.namelist()[0]
            racine = ET.fromstring(archive.read(nom_xml))
        points = racine.findall("pdv")
        # Mêmes stations d'un fichier à l'autre : celles du premier fichier.
        retenues = retenues or stations_retenues(points)
        for pdv in points:
            if pdv.get("id") not in retenues:
                racine.remove(pdv)
        xml = ET.tostring(racine, encoding="ISO-8859-1", xml_declaration=True)
        sortie = DESTINATION / chemin.name
        with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(nom_xml, xml)
        print(
            f"{sortie.name} : {len(racine.findall('pdv'))} stations, {sortie.stat().st_size} octets"
        )


if __name__ == "__main__":
    main([Path(argument) for argument in sys.argv[1:]])
