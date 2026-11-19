"""DAG quotidien : ingestion du flux officiel des prix des carburants dans l'entrepôt.

Chaque matin à 6 h (heure de Paris), le DAG ingère le fichier de la veille, publié
vers 23 h 25. Il est idempotent : rejouer une date remplace ses données sans doublon.

Rejouer un jour précis : déclencher le DAG avec la configuration
``{"date_fichier": "AAAA-MM-JJ"}``. Rattraper une période :
``airflow backfill create --dag-id prix_carburants_quotidien --from-date ... --to-date ...``
(chaque date logique ingère la veille).

Après le chargement, dbt vérifie la fraîcheur de la source puis reconstruit et teste
les couches staging, intermediate et marts. Un test dbt en erreur fait échouer le DAG :
les marts ne sont pas mis à jour avec des données douteuses.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import Param, dag, get_current_context, task
from airflow.sdk.exceptions import AirflowFailException
from airflow.timetables.trigger import CronTriggerTimetable

FUSEAU = "Europe/Paris"
ID_CONNEXION_ENTREPOT = "entrepot"

# dbt tourne dans son environnement virtuel ; les dépendances (dbt_utils) ne sont
# téléchargées qu'au premier passage. Variables fournies par l'image et par Compose.
COMMANDE_DBT = (
    'cd "$DBT_PROJECT_DIR" '
    '&& { [ -d dbt_packages/dbt_utils ] || "$DBT_BIN" deps; } '
    '&& "$DBT_BIN" {sous_commande}'
)

DOCUMENTATION = """
### Prix des carburants : ingestion quotidienne

| Tâche | Rôle |
|---|---|
| `choisir_date` | date à ingérer : la veille de la date logique, ou `date_fichier` si imposée |
| `telecharger` | ZIP du jour vers la zone d'atterrissage, signature vérifiée |
| `charger_raw` | analyse du XML, remplacement de la date dans le schéma `raw` |
| `dbt_fraicheur_source` | `dbt source freshness` : le journal d'ingestion est-il à jour ? |
| `dbt_build` | modèles et tests dbt ; un test en erreur arrête la mise à jour des marts |

Source : [prix-carburants.gouv.fr](https://www.prix-carburants.gouv.fr/rubrique/opendata/),
environ un mois de fichiers disponibles.
"""


@dag(
    dag_id="prix_carburants_quotidien",
    description="Ingestion quotidienne des prix des carburants (flux officiel) dans PostgreSQL",
    schedule=CronTriggerTimetable("0 6 * * *", timezone=FUSEAU),
    start_date=pendulum.datetime(2026, 10, 1, tz=FUSEAU),
    catchup=False,
    # Une seule exécution à la fois : la VM Docker a peu de mémoire et chaque
    # exécution remplace les données d'une date entière.
    max_active_runs=1,
    params={
        "date_fichier": Param(
            None,
            type=["null", "string"],
            format="date",
            description="Date du fichier à ingérer (AAAA-MM-JJ). Vide : la veille.",
        )
    },
    default_args={
        "owner": "data",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=15),
    },
    doc_md=DOCUMENTATION,
    tags=["carburants", "ingestion"],
)
def prix_carburants_quotidien():
    @task
    def choisir_date() -> str:
        from fuel_prices.dates import date_a_ingerer, est_hors_retention
        from fuel_prices.ingestion import verifier_date_passee

        contexte = get_current_context()
        # Dans Airflow 3, un déclenchement manuel peut n'avoir aucune date logique : la clé
        # est alors absente du contexte. On prend l'heure à laquelle l'exécution a été demandée.
        date_logique: datetime = contexte.get("logical_date") or contexte["dag_run"].run_after
        try:
            jour = date_a_ingerer(date_logique, contexte["params"].get("date_fichier"))
            verifier_date_passee(jour)
        except ValueError as erreur:
            raise AirflowFailException(str(erreur)) from erreur
        if est_hors_retention(jour, pendulum.now(FUSEAU).date()):
            # Inutile de réessayer : la source a supprimé ce fichier.
            raise AirflowFailException(
                f"Le fichier du {jour:%d/%m/%Y} est sorti de la fenêtre de rétention de la source."
            )
        return jour.isoformat()

    @task(retries=3, retry_delay=timedelta(minutes=30))
    def telecharger(jour_iso: str) -> dict:
        # Réessais espacés : si la source publie en retard, le fichier finit par arriver.
        from datetime import date

        from fuel_prices.telechargement import URL_BASE_PAR_DEFAUT, telecharger_jour

        fichier = telecharger_jour(
            date.fromisoformat(jour_iso),
            Path(os.environ.get("DOSSIER_DONNEES", "/opt/airflow/data")),
            os.environ.get("SOURCE_URL_JOUR", URL_BASE_PAR_DEFAUT),
        )
        return {
            "chemin": str(fichier.chemin),
            "sha256": fichier.sha256,
            "taille_octets": fichier.taille_octets,
            "deja_present": fichier.deja_present,
        }

    @task
    def charger_raw(jour_iso: str, fichier: dict) -> dict:
        from datetime import date

        from fuel_prices.connexions import connexion_depuis_airflow
        from fuel_prices.ingestion import charger_fichier
        from fuel_prices.telechargement import FichierTelecharge

        telecharge = FichierTelecharge(
            chemin=Path(fichier["chemin"]),
            sha256=fichier["sha256"],
            taille_octets=fichier["taille_octets"],
            deja_present=fichier["deja_present"],
        )
        connexion = connexion_depuis_airflow(ID_CONNEXION_ENTREPOT)
        try:
            comptes = charger_fichier(date.fromisoformat(jour_iso), connexion, telecharge)
        finally:
            connexion.close()
        return {"date_fichier": jour_iso, **comptes}

    fraicheur = BashOperator(
        task_id="dbt_fraicheur_source",
        bash_command=COMMANDE_DBT.replace("{sous_commande}", "source freshness"),
        retries=0,
    )
    build = BashOperator(
        task_id="dbt_build",
        bash_command=COMMANDE_DBT.replace("{sous_commande}", "build"),
        # Un test en échec signale un problème de données : réessayer ne le corrigera pas.
        retries=0,
        execution_timeout=timedelta(minutes=20),
    )

    jour = choisir_date()
    charger_raw(jour, telecharger(jour)) >> fraicheur >> build


prix_carburants_quotidien()
