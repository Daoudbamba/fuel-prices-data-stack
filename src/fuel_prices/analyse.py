"""Lecture du XML quotidien des prix des carburants.

Structure du fichier (vérifiée sur les fichiers de novembre 2026) :

    <pdv_liste>
      <pdv id="1000001" latitude="4620138" longitude="519829" cp="01000" pop="R">
        <adresse>...</adresse>
        <ville>...</ville>
        <horaires automate-24-24="1"> <jour .../> ... </horaires>
        <services> <service>...</service> ... </services>
        <prix nom="Gazole" id="1" maj="2026-11-17T20:00:00" valeur="2.086"/>
        <rupture id="4" nom="GPLc" debut="..." fin="" type="definitive"/>
        <fermeture type="T" debut="..." fin=""/>
      </pdv>
    </pdv_liste>

Choix de la couche raw : les valeurs restent du texte, telles qu'écrites dans le fichier
(attribut vide → NULL). Les conversions de types, d'unités et les contrôles de qualité
sont le travail des modèles dbt de staging : une valeur aberrante doit arriver jusqu'aux
tests dbt au lieu d'être corrigée en silence ici.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class Station:
    id_station: str
    latitude: str | None
    longitude: str | None
    code_postal: str | None
    type_route: str | None  # pop : R = route, A = autoroute
    adresse: str | None
    ville: str | None
    automate_24_24: str | None
    services: str  # tableau JSON des libellés de services
    fermeture_type: str | None
    fermeture_debut: str | None
    fermeture_fin: str | None


@dataclass(frozen=True)
class Prix:
    id_station: str
    id_carburant: str | None
    carburant: str | None
    maj: str | None
    valeur: str | None


@dataclass(frozen=True)
class Rupture:
    id_station: str
    id_carburant: str | None
    carburant: str | None
    debut: str | None
    fin: str | None
    type_rupture: str | None


@dataclass
class ContenuJour:
    stations: list[Station] = field(default_factory=list)
    prix: list[Prix] = field(default_factory=list)
    ruptures: list[Rupture] = field(default_factory=list)


def _vide_en_none(valeur: str | None) -> str | None:
    """Les attributs absents ou vides deviennent NULL ; le reste est gardé tel quel."""
    if valeur is None:
        return None
    valeur = valeur.strip()
    return valeur or None


def _texte(element: ET.Element, balise: str) -> str | None:
    enfant = element.find(balise)
    return _vide_en_none(enfant.text) if enfant is not None else None


def _lire_station(pdv: ET.Element) -> tuple[Station, list[Prix], list[Rupture]]:
    id_station = pdv.get("id")
    if not id_station:
        raise ValueError("Point de vente sans identifiant dans le fichier source.")

    horaires = pdv.find("horaires")
    fermeture = pdv.find("fermeture")
    services = [
        s.text.strip() for s in pdv.findall("services/service") if s.text and s.text.strip()
    ]

    station = Station(
        id_station=id_station,
        latitude=_vide_en_none(pdv.get("latitude")),
        longitude=_vide_en_none(pdv.get("longitude")),
        code_postal=_vide_en_none(pdv.get("cp")),
        type_route=_vide_en_none(pdv.get("pop")),
        adresse=_texte(pdv, "adresse"),
        ville=_texte(pdv, "ville"),
        automate_24_24=(
            _vide_en_none(horaires.get("automate-24-24")) if horaires is not None else None
        ),
        services=json.dumps(services, ensure_ascii=False),
        fermeture_type=_vide_en_none(fermeture.get("type")) if fermeture is not None else None,
        fermeture_debut=_vide_en_none(fermeture.get("debut")) if fermeture is not None else None,
        fermeture_fin=_vide_en_none(fermeture.get("fin")) if fermeture is not None else None,
    )
    prix = [
        Prix(
            id_station=id_station,
            id_carburant=_vide_en_none(p.get("id")),
            carburant=_vide_en_none(p.get("nom")),
            maj=_vide_en_none(p.get("maj")),
            valeur=_vide_en_none(p.get("valeur")),
        )
        for p in pdv.findall("prix")
    ]
    ruptures = [
        Rupture(
            id_station=id_station,
            id_carburant=_vide_en_none(r.get("id")),
            carburant=_vide_en_none(r.get("nom")),
            debut=_vide_en_none(r.get("debut")),
            fin=_vide_en_none(r.get("fin")),
            type_rupture=_vide_en_none(r.get("type")),
        )
        for r in pdv.findall("rupture")
    ]
    return station, prix, ruptures


def iterer_points_de_vente(flux: IO[bytes]) -> Iterator[ET.Element]:
    """Parcourt les <pdv> un par un et libère chacun après usage (mémoire constante).

    L'encodage (ISO-8859-1) est lu dans la déclaration XML par le parseur.
    """
    for _evenement, element in ET.iterparse(flux, events=("end",)):
        if element.tag == "pdv":
            yield element
            element.clear()


def analyser_xml(flux: IO[bytes]) -> ContenuJour:
    contenu = ContenuJour()
    for pdv in iterer_points_de_vente(flux):
        station, prix, ruptures = _lire_station(pdv)
        contenu.stations.append(station)
        contenu.prix.extend(prix)
        contenu.ruptures.extend(ruptures)
    if not contenu.stations:
        raise ValueError("Le fichier ne contient aucun point de vente.")
    return contenu


def analyser_zip(chemin: Path) -> ContenuJour:
    """Ouvre le ZIP quotidien, qui contient un seul fichier XML."""
    with zipfile.ZipFile(chemin) as archive:
        xml = [nom for nom in archive.namelist() if nom.lower().endswith(".xml")]
        if len(xml) != 1:
            raise ValueError(f"Archive inattendue : {len(xml)} fichier(s) XML dans {chemin.name}.")
        with archive.open(xml[0]) as flux:
            return analyser_xml(flux)
