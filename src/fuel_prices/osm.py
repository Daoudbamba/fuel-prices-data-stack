"""Enseignes des stations, extraites d'OpenStreetMap.

Le flux officiel ne donne pas l'enseigne des stations. OpenStreetMap la donne (tag
``brand``) et relie chaque station au flux par le tag ``ref:FR:prix-carburants``, qui
porte l'identifiant officiel. L'extraction passe par l'API Overpass.

Données © contributeurs OpenStreetMap, sous licence ODbL : l'attribution est due
partout où ces données sont affichées (README, tableau de bord).

Comme pour le flux quotidien, la couche raw garde les libellés tels quels :
la normalisation (« Total », « Total Energies » → TotalEnergies) se fait dans dbt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from fuel_prices.chargement import vers_csv

journal = logging.getLogger(__name__)

URL_OVERPASS_PAR_DEFAUT = "https://overpass-api.de/api/interpreter"
DELAI_OVERPASS_S = 180

# Toutes les stations-service de France reliées au flux officiel, avec leurs seuls tags.
REQUETE_OVERPASS = """
[out:json][timeout:170];
area["ISO3166-1"="FR"][admin_level=2]->.france;
nwr["amenity"="fuel"]["ref:FR:prix-carburants"](area.france);
out tags;
"""

DDL_OSM = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.osm_enseignes (
    date_extraction  date        NOT NULL,
    id_station       text        NOT NULL,
    type_osm         text        NOT NULL,
    id_osm           bigint      NOT NULL,
    marque           text,
    nom              text,
    operateur        text,
    marque_wikidata  text,
    charge_le        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS osm_enseignes_date_idx ON raw.osm_enseignes (date_extraction);
"""


class ExtractionOsmError(RuntimeError):
    """Réponse Overpass inexploitable (délai dépassé, résultat vide...)."""


@dataclass(frozen=True)
class EnseigneOsm:
    id_station: str
    type_osm: str
    id_osm: int
    marque: str | None
    nom: str | None
    operateur: str | None
    marque_wikidata: str | None


def _propre(valeur: str | None) -> str | None:
    if valeur is None:
        return None
    return valeur.strip() or None


def analyser_reponse(reponse: dict[str, Any], minimum_attendu: int = 1) -> list[EnseigneOsm]:
    """Une ligne par identifiant officiel : un objet OSM peut en porter plusieurs (« a;b »).

    Overpass signale un délai dépassé par un champ « remark » dans une réponse HTTP 200 :
    on refuse alors le résultat, probablement incomplet.
    """
    remarque = reponse.get("remark", "")
    if "runtime error" in remarque.lower():
        raise ExtractionOsmError(f"Overpass a interrompu la requête : {remarque}")

    lignes: list[EnseigneOsm] = []
    for element in reponse.get("elements", []):
        tags = element.get("tags", {})
        for reference in tags.get("ref:FR:prix-carburants", "").split(";"):
            reference = reference.strip()
            if not reference:
                continue
            lignes.append(
                EnseigneOsm(
                    id_station=reference,
                    type_osm=element["type"],
                    id_osm=int(element["id"]),
                    marque=_propre(tags.get("brand")),
                    nom=_propre(tags.get("name")),
                    operateur=_propre(tags.get("operator")),
                    marque_wikidata=_propre(tags.get("brand:wikidata")),
                )
            )
    if len(lignes) < minimum_attendu:
        raise ExtractionOsmError(
            f"{len(lignes)} station(s) reçue(s) d'Overpass, {minimum_attendu} attendue(s) au moins."
        )
    return lignes


def creer_session() -> requests.Session:
    """Session qui réessaie sur les erreurs passagères d'Overpass (502, 503, 504, 429).

    La requête Overpass est une lecture : la renvoyer en POST est sans risque, d'où
    l'autorisation explicite de POST, que urllib3 ne réessaie pas par défaut.
    """
    session = requests.Session()
    reessais = Retry(
        total=3,
        backoff_factor=10,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=("POST",),
    )
    session.mount("https://", HTTPAdapter(max_retries=reessais))
    return session


def extraire(
    url: str = URL_OVERPASS_PAR_DEFAUT,
    session: requests.Session | None = None,
    minimum_attendu: int = 9000,
) -> list[EnseigneOsm]:
    """Interroge Overpass. Environ 10 000 stations attendues pour la France."""
    session = session or creer_session()
    # Overpass refuse les requêtes sans User-Agent identifiable (HTTP 406).
    reponse = session.post(
        url,
        data={"data": REQUETE_OVERPASS},
        headers={"User-Agent": "fuel-prices-data-stack/0.1", "Accept": "application/json"},
        timeout=DELAI_OVERPASS_S,
    )
    reponse.raise_for_status()
    lignes = analyser_reponse(reponse.json(), minimum_attendu)
    journal.info("Overpass : %d références de stations extraites", len(lignes))
    return lignes


def charger(connexion: Any, jour: date, lignes: list[EnseigneOsm]) -> int:
    """Remplace l'extraction du jour dans raw.osm_enseignes (idempotent, transactionnel)."""
    colonnes = (
        "date_extraction, id_station, type_osm, id_osm, marque, nom, operateur, marque_wikidata"
    )
    with connexion, connexion.cursor() as curseur:
        curseur.execute(DDL_OSM)
        curseur.execute("DELETE FROM raw.osm_enseignes WHERE date_extraction = %s", (jour,))
        curseur.copy_expert(
            f"COPY raw.osm_enseignes ({colonnes}) FROM STDIN WITH (FORMAT csv)",
            vers_csv(jour, lignes),
        )
    return len(lignes)
