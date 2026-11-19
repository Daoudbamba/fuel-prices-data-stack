"""Tests du choix de la date à ingérer par le DAG."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from fuel_prices.dates import FUSEAU_SOURCE, date_a_ingerer, est_hors_retention


def test_execution_du_matin_ingere_la_veille():
    execution = datetime(2026, 11, 18, 6, 0, tzinfo=FUSEAU_SOURCE)
    assert date_a_ingerer(execution) == date(2026, 11, 17)


def test_date_logique_en_utc_convertie_en_heure_de_paris():
    # 23 h 30 UTC le 17 = 0 h 30 à Paris le 18 : la veille, à Paris, est le 17.
    execution = datetime(2026, 11, 17, 23, 30, tzinfo=UTC)
    assert date_a_ingerer(execution) == date(2026, 11, 17)


def test_passage_a_l_heure_d_ete():
    # Nuit du 28 au 29 mars 2026 : 6 h à Paris = 4 h UTC.
    execution = datetime(2026, 3, 29, 4, 0, tzinfo=UTC)
    assert date_a_ingerer(execution) == date(2026, 3, 28)


def test_date_imposee_prioritaire():
    execution = datetime(2026, 11, 18, 6, 0, tzinfo=FUSEAU_SOURCE)
    assert date_a_ingerer(execution, "2026-11-02") == date(2026, 11, 2)


def test_date_imposee_invalide_refusee():
    with pytest.raises(ValueError):
        date_a_ingerer(datetime(2026, 11, 18, tzinfo=UTC), "18/11/2026")


def test_date_logique_sans_fuseau_refusee():
    with pytest.raises(ValueError, match="fuseau"):
        date_a_ingerer(datetime(2026, 11, 18, 6, 0))


@pytest.mark.parametrize(
    ("jour", "attendu"),
    [(date(2026, 11, 17), False), (date(2026, 10, 14), False), (date(2026, 10, 13), True)],
)
def test_retention(jour: date, attendu: bool):
    assert est_hors_retention(jour, aujourd_hui=date(2026, 11, 18)) is attendu
