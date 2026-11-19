"""DAG hebdomadaire : enseignes des stations depuis OpenStreetMap.

Le flux officiel ne donne pas l'enseigne des stations. Chaque lundi, ce DAG extrait
d'OpenStreetMap (API Overpass) la marque de chaque station reliée au flux par le tag
``ref:FR:prix-carburants``, puis reconstruit les modèles dbt qui en dépendent.

Hebdomadaire et non quotidien : les enseignes changent rarement, et Overpass est un
service communautaire gratuit à solliciter avec modération.
Données © contributeurs OpenStreetMap, licence ODbL.
"""

from __future__ import annotations

import os
from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task
from airflow.timetables.trigger import CronTriggerTimetable

FUSEAU = "Europe/Paris"
ID_CONNEXION_ENTREPOT = "entrepot"


@dag(
    dag_id="enseignes_osm_hebdomadaire",
    description="Enseignes des stations-service extraites d'OpenStreetMap (Overpass)",
    schedule=CronTriggerTimetable("0 5 * * 1", timezone=FUSEAU),
    start_date=pendulum.datetime(2026, 11, 1, tz=FUSEAU),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "data",
        # Overpass est parfois saturé : on réessaie plus tard plutôt que d'insister.
        "retries": 3,
        "retry_delay": timedelta(minutes=20),
        "execution_timeout": timedelta(minutes=10),
    },
    doc_md=__doc__,
    tags=["carburants", "ingestion", "osm"],
)
def enseignes_osm_hebdomadaire():
    @task
    def extraire_et_charger() -> dict:
        from fuel_prices.connexions import connexion_depuis_airflow
        from fuel_prices.osm import URL_OVERPASS_PAR_DEFAUT, charger, extraire

        jour = pendulum.now(FUSEAU).date()
        lignes = extraire(os.environ.get("OVERPASS_URL", URL_OVERPASS_PAR_DEFAUT))
        connexion = connexion_depuis_airflow(ID_CONNEXION_ENTREPOT)
        try:
            nb = charger(connexion, jour, lignes)
        finally:
            connexion.close()
        return {
            "date_extraction": jour.isoformat(),
            "references": nb,
            "avec_marque": sum(1 for ligne in lignes if ligne.marque),
        }

    # Seuls les modèles en aval des enseignes sont reconstruits et testés.
    dbt_enseignes = BashOperator(
        task_id="dbt_build_enseignes",
        bash_command=(
            'cd "$DBT_PROJECT_DIR" '
            '&& { [ -d dbt_packages/dbt_utils ] || "$DBT_BIN" deps; } '
            '&& "$DBT_BIN" build --select "source:osm+"'
        ),
        retries=0,
        execution_timeout=timedelta(minutes=20),
    )

    extraire_et_charger() >> dbt_enseignes


enseignes_osm_hebdomadaire()
