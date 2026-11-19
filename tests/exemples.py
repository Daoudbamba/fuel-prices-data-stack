"""Données de test : extrait réaliste du fichier source et faux client HTTP."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import date

# Extrait construit d'après la structure réelle du fichier du 17/11/2026, encodé comme
# l'original en ISO-8859-1. Il couvre les cas rencontrés dans la source :
#   - 1000001 : station complète, accent dans la ville, rupture définitive ;
#   - 1000002 : virgule et guillemets dans l'adresse, pas de bloc horaires ;
#   - 2000003 : autoroute (pop="A"), Corse, aucun prix, fermeture temporaire ;
#   - 9700004 : DOM, prix au mauvais format (valeur vide), qui doit rester NULL.
XML_EXEMPLE = """<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<pdv_liste>
  <pdv id="1000001" latitude="4620138" longitude="519829" cp="01000" pop="R">
    <adresse>596 AVENUE DE TREVOUX</adresse>
    <ville>SAINT-DENIS-LÈS-BOURG</ville>
    <horaires automate-24-24="1">
      <jour id="1" nom="Lundi" ferme=""><horaire ouverture="08.30" fermeture="19.00"/></jour>
    </horaires>
    <services>
      <service>DAB (Distributeur automatique de billets)</service>
      <service>Station de gonflage</service>
    </services>
    <prix nom="Gazole" id="1" maj="2026-11-17T20:00:00" valeur="2.086"/>
    <prix nom="E10" id="5" maj="2026-11-17T20:00:00" valeur="1.969"/>
    <rupture id="4" nom="GPLc" debut="2017-09-16T09:50:23" fin="" type="definitive"/>
  </pdv>
  <pdv id="1000002" latitude="4621855" longitude="522805" cp="01000" pop="R">
    <adresse>16 Avenue de Marboz, lieu-dit "Les Vennes"</adresse>
    <ville>BOURG-EN-BRESSE</ville>
    <services/>
    <prix nom="SP98" id="6" maj="2026-11-16T11:12:01" valeur="2.076"/>
  </pdv>
  <pdv id="2000003" latitude="4192000" longitude="873000" cp="20000" pop="A">
    <adresse>RN 193</adresse>
    <ville>Ajaccio</ville>
    <services><service>Boutique alimentaire</service></services>
    <fermeture type="T" debut="2026-11-01T00:00:00" fin=""/>
  </pdv>
  <pdv id="9700004" latitude="" longitude="" cp="97100" pop="R">
    <adresse>Route de la Plage</adresse>
    <ville>Basse-Terre</ville>
    <services/>
    <prix nom="Gazole" id="1" maj="2026-11-17T08:00:00" valeur=""/>
  </pdv>
</pdv_liste>
"""

JOUR_EXEMPLE = date(2026, 11, 17)


def octets_xml() -> bytes:
    return XML_EXEMPLE.encode("iso-8859-1")


def octets_zip(
    xml: bytes | None = None, nom: str = "PrixCarburants_quotidien_20261117.xml"
) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(nom, octets_xml() if xml is None else xml)
    return tampon.getvalue()


# Date fictive réservée aux tests d'intégration, hors de toute période réelle.
JOUR_TEST = date(2000, 1, 1)


@dataclass
class FausseReponse:
    content: bytes
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}")


@dataclass
class FausseSession:
    """Client HTTP de test : renvoie une réponse fixe et note les URL appelées."""

    reponse: FausseReponse
    appels: list[str] = field(default_factory=list)

    def get(self, url: str, timeout: float) -> FausseReponse:
        self.appels.append(url)
        return self.reponse
