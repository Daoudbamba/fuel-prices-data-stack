"""Fixtures partagées par les tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from exemples import JOUR_TEST, FausseReponse, FausseSession, octets_zip


@pytest.fixture
def zip_exemple(tmp_path: Path) -> Path:
    chemin = tmp_path / "exemple.zip"
    chemin.write_bytes(octets_zip())
    return chemin


@pytest.fixture
def session_zip() -> FausseSession:
    return FausseSession(FausseReponse(octets_zip(), headers={"Content-Type": "application/zip"}))


@pytest.fixture
def session_html() -> FausseSession:
    # Comportement réel de la source pour une date absente : HTTP 200 et page HTML.
    page = "<!DOCTYPE html><html lang=fr><head><title>Prix carburants</title></head></html>"
    return FausseSession(
        FausseReponse(page.encode(), headers={"Content-Type": "text/html; charset=UTF-8"})
    )


@pytest.fixture
def connexion_entrepot():
    """Connexion à un PostgreSQL de test (stack locale ou service de la CI).

    Les tests marqués « integration » sont ignorés si ENTREPOT_PASSWORD n'est pas défini.
    Ils n'écrivent qu'à la date fictive JOUR_TEST, nettoyée avant et après : lancés contre
    l'entrepôt local, ils ne touchent pas aux vraies données ingérées.
    """
    if "ENTREPOT_PASSWORD" not in os.environ:
        pytest.skip("ENTREPOT_PASSWORD absent : pas de base PostgreSQL de test.")
    from fuel_prices.ingestion import connexion_depuis_environnement

    connexion = connexion_depuis_environnement()
    _nettoyer_jour_test(connexion)
    yield connexion
    _nettoyer_jour_test(connexion)
    connexion.close()


def _nettoyer_jour_test(connexion) -> None:
    with connexion, connexion.cursor() as curseur:
        curseur.execute("SELECT to_regclass('raw.journal_ingestion') IS NOT NULL")
        if not curseur.fetchone()[0]:
            return
        for table in ("raw.stations", "raw.prix", "raw.ruptures", "raw.journal_ingestion"):
            curseur.execute(f"DELETE FROM {table} WHERE date_fichier = %s", (JOUR_TEST,))
