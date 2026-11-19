"""Tests de l'extraction des enseignes OpenStreetMap (sans réseau)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from exemples import JOUR_TEST
from fuel_prices.osm import ExtractionOsmError, analyser_reponse, charger, extraire

# Extrait au format réel d'Overpass (out tags) : un nœud, une voie portant deux
# références, un objet sans marque et un objet sans référence exploitable.
REPONSE_OVERPASS = {
    "version": 0.6,
    "elements": [
        {
            "type": "node",
            "id": 25209297,
            "tags": {
                "amenity": "fuel",
                "brand": "Intermarché",
                "brand:wikidata": "Q3153200",
                "name": "Intermarché ",
                "ref:FR:prix-carburants": "13180001",
            },
        },
        {
            "type": "way",
            "id": 1483913390,
            "tags": {
                "amenity": "fuel",
                "brand": "TotalEnergies",
                "operator": "SARL Exemple",
                "ref:FR:prix-carburants": "13710001; 13710002",
            },
        },
        {"type": "node", "id": 4374143015, "tags": {"ref:FR:prix-carburants": "13180001"}},
        {"type": "node", "id": 7, "tags": {"brand": "Esso", "ref:FR:prix-carburants": ""}},
    ],
}


def test_une_ligne_par_reference():
    lignes = analyser_reponse(REPONSE_OVERPASS)
    assert [(ligne.id_station, ligne.id_osm) for ligne in lignes] == [
        ("13180001", 25209297),
        ("13710001", 1483913390),
        ("13710002", 1483913390),
        ("13180001", 4374143015),
    ]


def test_tags_nettoyes_et_absents_en_none():
    premiere, voie, _, sans_marque = analyser_reponse(REPONSE_OVERPASS)
    assert premiere.nom == "Intermarché"  # espace final retiré
    assert premiere.marque_wikidata == "Q3153200"
    assert (voie.type_osm, voie.operateur) == ("way", "SARL Exemple")
    assert sans_marque.marque is None and sans_marque.nom is None


def test_delai_overpass_depasse_refuse():
    reponse = {"elements": [], "remark": 'runtime error: Query timed out in "query"'}
    with pytest.raises(ExtractionOsmError, match="interrompu"):
        analyser_reponse(reponse)


def test_resultat_trop_petit_refuse():
    with pytest.raises(ExtractionOsmError, match="9000 attendue"):
        analyser_reponse(REPONSE_OVERPASS, minimum_attendu=9000)


@dataclass
class FausseReponseJson:
    donnees: dict
    status_code: int = 200

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self.donnees


@dataclass
class FausseSessionPost:
    appels: list[dict] = field(default_factory=list)

    def post(self, url: str, data: dict, headers: dict, timeout: float) -> FausseReponseJson:
        self.appels.append({"url": url, "data": data, "headers": headers})
        return FausseReponseJson(REPONSE_OVERPASS)


def test_requete_envoyee_avec_user_agent():
    session = FausseSessionPost()
    extraire("https://overpass.test/api", session=session, minimum_attendu=1)
    appel = session.appels[0]
    assert appel["url"] == "https://overpass.test/api"
    assert "ref:FR:prix-carburants" in appel["data"]["data"]
    assert appel["headers"]["User-Agent"]  # sans lui, Overpass répond HTTP 406


@pytest.mark.integration
def test_chargement_idempotent(connexion_entrepot):
    lignes = analyser_reponse(REPONSE_OVERPASS)
    try:
        for _ in range(2):
            assert charger(connexion_entrepot, JOUR_TEST, lignes) == 4
        with connexion_entrepot.cursor() as curseur:
            curseur.execute(
                "SELECT count(*), count(marque) FROM raw.osm_enseignes WHERE date_extraction = %s",
                (JOUR_TEST,),
            )
            assert curseur.fetchone() == (4, 3)
    finally:
        with connexion_entrepot, connexion_entrepot.cursor() as curseur:
            curseur.execute(
                "DELETE FROM raw.osm_enseignes WHERE date_extraction = %s", (JOUR_TEST,)
            )
