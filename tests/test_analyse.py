"""Tests de la lecture du XML source."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from exemples import octets_xml, octets_zip
from fuel_prices.analyse import analyser_xml, analyser_zip


@pytest.fixture
def contenu():
    return analyser_xml(io.BytesIO(octets_xml()))


def test_compte_stations_prix_ruptures(contenu):
    assert len(contenu.stations) == 4
    assert len(contenu.prix) == 4
    assert len(contenu.ruptures) == 1


def test_encodage_iso_8859_1_decode(contenu):
    # Le fichier source est en ISO-8859-1 : les accents doivent survivre à la lecture.
    assert contenu.stations[0].ville == "SAINT-DENIS-LÈS-BOURG"


def test_valeurs_gardees_en_texte_brut(contenu):
    # Coordonnées multipliées par 100 000 et prix : la conversion est faite dans dbt.
    station = contenu.stations[0]
    assert (station.latitude, station.longitude) == ("4620138", "519829")
    gazole = contenu.prix[0]
    assert (gazole.id_station, gazole.carburant, gazole.id_carburant) == ("1000001", "Gazole", "1")
    assert (gazole.maj, gazole.valeur) == ("2026-11-17T20:00:00", "2.086")


def test_attributs_vides_deviennent_null(contenu):
    dom = next(s for s in contenu.stations if s.id_station == "9700004")
    assert dom.latitude is None and dom.longitude is None
    prix_dom = next(p for p in contenu.prix if p.id_station == "9700004")
    assert prix_dom.valeur is None
    rupture = contenu.ruptures[0]
    assert rupture.fin is None and rupture.type_rupture == "definitive"


def test_services_en_tableau_json(contenu):
    assert json.loads(contenu.stations[0].services) == [
        "DAB (Distributeur automatique de billets)",
        "Station de gonflage",
    ]
    assert json.loads(contenu.stations[1].services) == []


def test_horaires_et_fermeture(contenu):
    par_id = {s.id_station: s for s in contenu.stations}
    assert par_id["1000001"].automate_24_24 == "1"
    assert par_id["1000002"].automate_24_24 is None  # pas de bloc <horaires>
    corse = par_id["2000003"]
    assert (corse.type_route, corse.fermeture_type, corse.fermeture_fin) == ("A", "T", None)


def test_station_sans_prix_est_gardee(contenu):
    # 448 stations sur 9 954 n'ont aucun prix dans le fichier réel du 17/11/2026.
    assert "2000003" in {s.id_station for s in contenu.stations}
    assert "2000003" not in {p.id_station for p in contenu.prix}


def test_fichier_sans_point_de_vente_refuse():
    vide = b'<?xml version="1.0" encoding="ISO-8859-1"?><pdv_liste></pdv_liste>'
    with pytest.raises(ValueError, match="aucun point de vente"):
        analyser_xml(io.BytesIO(vide))


def test_point_de_vente_sans_identifiant_refuse():
    xml = b'<?xml version="1.0" encoding="ISO-8859-1"?><pdv_liste><pdv cp="01000"/></pdv_liste>'
    with pytest.raises(ValueError, match="sans identifiant"):
        analyser_xml(io.BytesIO(xml))


def test_analyse_du_zip(zip_exemple: Path):
    assert len(analyser_zip(zip_exemple).stations) == 4


def test_zip_sans_xml_refuse(tmp_path: Path):
    chemin = tmp_path / "vide.zip"
    with zipfile.ZipFile(chemin, "w") as archive:
        archive.writestr("lisezmoi.txt", "rien")
    with pytest.raises(ValueError, match="0 fichier"):
        analyser_zip(chemin)


def test_xml_tronque_refuse(tmp_path: Path):
    chemin = tmp_path / "tronque.zip"
    chemin.write_bytes(octets_zip(octets_xml()[:-200]))
    with pytest.raises(Exception, match="no element found|unclosed token|mismatched tag"):
        analyser_zip(chemin)
