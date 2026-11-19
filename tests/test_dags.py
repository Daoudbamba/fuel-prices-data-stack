"""Intégrité des DAG : ils s'importent sans erreur et gardent la structure attendue.

Ces tests ont besoin d'Airflow : ils sont ignorés dans l'environnement virtuel local et
tournent en CI dans l'image Airflow du projet (aucune base de métadonnées n'est requise).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# On vise un module précis : le dossier airflow/ du projet (qui contient les DAG) serait
# sinon pris pour le paquet Airflow, et l'import « réussirait » à tort.
DagBag = pytest.importorskip("airflow.dag_processing.dagbag").DagBag

DOSSIER_DAGS = Path(__file__).resolve().parent.parent / "airflow" / "dags"


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DOSSIER_DAGS))


def test_aucune_erreur_d_import(dagbag: DagBag):
    assert dagbag.import_errors == {}


def test_dag_quotidien(dagbag: DagBag):
    dag = dagbag.dags["prix_carburants_quotidien"]
    assert dag.timetable.summary == "0 6 * * *"
    assert dag.max_active_runs == 1
    assert dag.catchup is False
    # Ordre de la chaîne : ingestion, puis fraîcheur de la source, puis dbt.
    ordre = ["choisir_date", "telecharger", "charger_raw", "dbt_fraicheur_source", "dbt_build"]
    for amont, aval in zip(ordre, ordre[1:], strict=False):
        assert aval in dag.get_task(amont).downstream_task_ids, f"{amont} → {aval}"
    assert dag.get_task("dbt_build").retries == 0


def test_dag_enseignes(dagbag: DagBag):
    dag = dagbag.dags["enseignes_osm_hebdomadaire"]
    assert dag.timetable.summary == "0 5 * * 1"
    assert "dbt_build_enseignes" in dag.get_task("extraire_et_charger").downstream_task_ids
    # Le référentiel des marques doit être reconstruit avec les modèles OSM.
    assert "correspondance_enseignes+" in dag.get_task("dbt_build_enseignes").bash_command
