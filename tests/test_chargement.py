"""Tests du chargement dans raw : sérialisation CSV (unitaire) et idempotence (intégration)."""

from __future__ import annotations

import csv
import dataclasses
import io
from datetime import date, timedelta
from pathlib import Path

import pytest

from exemples import JOUR_TEST, FausseSession, octets_xml
from fuel_prices.analyse import analyser_xml
from fuel_prices.chargement import charger_jour, colonnes, vers_csv
from fuel_prices.ingestion import ingerer_jour
from fuel_prices.telechargement import FichierTelecharge


@pytest.fixture
def contenu():
    return analyser_xml(io.BytesIO(octets_xml()))


def _fichier(tmp_path: Path) -> FichierTelecharge:
    return FichierTelecharge(tmp_path / "exemple.zip", "0" * 64, 1234, deja_present=False)


# --- Unitaires -----------------------------------------------------------------------


def test_csv_cite_virgules_et_guillemets(contenu):
    lignes = list(csv.reader(vers_csv(date(2026, 11, 17), contenu.stations)))
    adresse_attendue = '16 Avenue de Marboz, lieu-dit "Les Vennes"'
    station = next(ligne for ligne in lignes if ligne[1] == "1000002")
    assert station[colonnes(type(contenu.stations[0])).index("adresse")] == adresse_attendue


def test_csv_date_en_tete_et_null_vide(contenu):
    lignes = list(csv.reader(vers_csv(date(2026, 11, 17), contenu.prix)))
    assert all(ligne[0] == "2026-11-17" for ligne in lignes)
    prix_dom = next(ligne for ligne in lignes if ligne[1] == "9700004")
    assert prix_dom[-1] == ""  # valeur absente → champ vide → NULL pour COPY


def test_colonnes_dans_l_ordre_des_champs(contenu):
    assert colonnes(type(contenu.prix[0])) == [
        "date_fichier",
        "id_station",
        "id_carburant",
        "carburant",
        "maj",
        "valeur",
    ]


def test_date_du_jour_ou_future_refusee(tmp_path: Path):
    with pytest.raises(ValueError, match="fin de la journée"):
        ingerer_jour(date.today(), connexion=None, dossier=tmp_path)
    with pytest.raises(ValueError, match="fin de la journée"):
        ingerer_jour(date.today() + timedelta(days=1), connexion=None, dossier=tmp_path)


# --- Intégration (PostgreSQL) ----------------------------------------------------------


def _compter(connexion, table: str) -> int:
    with connexion.cursor() as curseur:
        curseur.execute(f"SELECT count(*) FROM {table} WHERE date_fichier = %s", (JOUR_TEST,))
        return curseur.fetchone()[0]


@pytest.mark.integration
def test_chargement_puis_rejeu_idempotent(connexion_entrepot, contenu, tmp_path: Path):
    for _ in range(2):
        comptes = charger_jour(connexion_entrepot, JOUR_TEST, contenu, _fichier(tmp_path))
    assert comptes == {"stations": 4, "prix": 4, "ruptures": 1}
    assert _compter(connexion_entrepot, "raw.stations") == 4
    assert _compter(connexion_entrepot, "raw.prix") == 4
    assert _compter(connexion_entrepot, "raw.ruptures") == 1
    assert _compter(connexion_entrepot, "raw.journal_ingestion") == 1


@pytest.mark.integration
def test_valeurs_et_null_en_base(connexion_entrepot, contenu, tmp_path: Path):
    charger_jour(connexion_entrepot, JOUR_TEST, contenu, _fichier(tmp_path))
    with connexion_entrepot.cursor() as curseur:
        curseur.execute(
            "SELECT ville, adresse, services->>0 FROM raw.stations "
            "WHERE date_fichier = %s AND id_station = '1000001'",
            (JOUR_TEST,),
        )
        assert curseur.fetchone() == (
            "SAINT-DENIS-LÈS-BOURG",
            "596 AVENUE DE TREVOUX",
            "DAB (Distributeur automatique de billets)",
        )
        curseur.execute(
            "SELECT valeur IS NULL FROM raw.prix "
            "WHERE date_fichier = %s AND id_station = '9700004'",
            (JOUR_TEST,),
        )
        assert curseur.fetchone() == (True,)


@pytest.mark.integration
def test_echec_en_cours_de_chargement_garde_l_etat_precedent(
    connexion_entrepot, contenu, tmp_path: Path
):
    charger_jour(connexion_entrepot, JOUR_TEST, contenu, _fichier(tmp_path))
    # services n'est pas du JSON valide : le COPY échoue après le DELETE de la date.
    station_cassee = dataclasses.replace(contenu.stations[0], services="pas du json")
    contenu_casse = dataclasses.replace(contenu, stations=[station_cassee])
    with pytest.raises(Exception, match="json"):
        charger_jour(connexion_entrepot, JOUR_TEST, contenu_casse, _fichier(tmp_path))
    assert _compter(connexion_entrepot, "raw.stations") == 4


@pytest.mark.integration
def test_ingestion_de_bout_en_bout(connexion_entrepot, session_zip: FausseSession, tmp_path: Path):
    statistiques = ingerer_jour(JOUR_TEST, connexion_entrepot, tmp_path, session=session_zip)
    assert session_zip.appels == ["https://donnees.roulez-eco.fr/opendata/jour/20000101"]
    assert (statistiques["stations"], statistiques["prix"], statistiques["ruptures"]) == (4, 4, 1)
    with connexion_entrepot.cursor() as curseur:
        curseur.execute(
            "SELECT nom_fichier, nb_stations FROM raw.journal_ingestion WHERE date_fichier = %s",
            (JOUR_TEST,),
        )
        assert curseur.fetchone() == ("PrixCarburants_quotidien_20000101.zip", 4)
