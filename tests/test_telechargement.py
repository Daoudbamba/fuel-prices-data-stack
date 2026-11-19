"""Tests du téléchargement, sans appel réseau (client HTTP simulé)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import requests

from exemples import JOUR_EXEMPLE, FausseReponse, FausseSession, octets_zip
from fuel_prices.telechargement import (
    SourceIndisponibleError,
    chemin_atterrissage,
    est_un_zip,
    telecharger_jour,
)


def test_url_et_chemin_partitionne(tmp_path: Path, session_zip: FausseSession):
    fichier = telecharger_jour(JOUR_EXEMPLE, tmp_path, "https://exemple.test/jour/", session_zip)
    assert session_zip.appels == ["https://exemple.test/jour/20261117"]
    attendu = tmp_path / "annee=2026" / "mois=11" / "PrixCarburants_quotidien_20261117.zip"
    assert fichier.chemin == attendu
    assert attendu.read_bytes() == octets_zip()
    assert fichier.sha256 == hashlib.sha256(octets_zip()).hexdigest()
    assert fichier.deja_present is False
    assert not list(tmp_path.rglob("*.part")), "le fichier temporaire doit être renommé"


def test_page_html_au_lieu_du_zip_est_detectee(tmp_path: Path, session_html: FausseSession):
    # La source répond HTTP 200 avec une page HTML pour une date non publiée.
    with pytest.raises(SourceIndisponibleError, match="17/11/2026.*text/html"):
        telecharger_jour(JOUR_EXEMPLE, tmp_path, session=session_html)
    assert not chemin_atterrissage(tmp_path, JOUR_EXEMPLE).exists()


def test_erreur_http_remontee(tmp_path: Path):
    session = FausseSession(FausseReponse(b"", status_code=503))
    with pytest.raises(requests.HTTPError):
        telecharger_jour(JOUR_EXEMPLE, tmp_path, session=session)


def test_fichier_present_reutilise_sans_reseau(tmp_path: Path, session_zip: FausseSession):
    telecharger_jour(JOUR_EXEMPLE, tmp_path, session=session_zip)
    second = telecharger_jour(JOUR_EXEMPLE, tmp_path, session=session_zip)
    assert len(session_zip.appels) == 1
    assert second.deja_present is True


def test_forcer_retelecharge(tmp_path: Path, session_zip: FausseSession):
    telecharger_jour(JOUR_EXEMPLE, tmp_path, session=session_zip)
    telecharger_jour(JOUR_EXEMPLE, tmp_path, session=session_zip, forcer=True)
    assert len(session_zip.appels) == 2


def test_fichier_present_mais_corrompu_retelecharge(tmp_path: Path, session_zip: FausseSession):
    cible = chemin_atterrissage(tmp_path, JOUR_EXEMPLE)
    cible.parent.mkdir(parents=True)
    cible.write_bytes(b"<html>page enregistree par erreur</html>")
    fichier = telecharger_jour(JOUR_EXEMPLE, tmp_path, session=session_zip)
    assert len(session_zip.appels) == 1
    assert est_un_zip(fichier.chemin.read_bytes())


@pytest.mark.parametrize(
    ("contenu", "attendu"),
    [(octets_zip(), True), (b"<!DOCTYPE html>", False), (b"", False)],
)
def test_signature_zip(contenu: bytes, attendu: bool):
    assert est_un_zip(contenu) is attendu
