"""Point d'entrée de l'ingestion d'un jour : téléchargement, analyse, chargement.

Le DAG Airflow appelle ``verifier_date_passee``, puis ``telecharger_jour`` et
``charger_fichier`` dans deux tâches distinctes. On peut aussi tout lancer à la main :

    python -m fuel_prices.ingestion --date 2026-11-17

La connexion à l'entrepôt est lue dans les variables ENTREPOT_HOST, ENTREPOT_PORT,
ENTREPOT_DB, ENTREPOT_USER et ENTREPOT_PASSWORD.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fuel_prices.analyse import analyser_zip
from fuel_prices.chargement import charger_jour
from fuel_prices.dates import FUSEAU_SOURCE
from fuel_prices.telechargement import URL_BASE_PAR_DEFAUT, FichierTelecharge, telecharger_jour

journal = logging.getLogger(__name__)


def verifier_date_passee(jour: date, aujourd_hui: date | None = None) -> None:
    """Refuse le jour en cours (heure de Paris) et les jours futurs."""
    aujourd_hui = aujourd_hui or datetime.now(FUSEAU_SOURCE).date()
    if jour >= aujourd_hui:
        raise ValueError(
            f"Le fichier du {jour:%d/%m/%Y} n'est complet qu'à la fin de la journée : "
            "ingérer une date passée."
        )


def charger_fichier(jour: date, connexion: Any, fichier: FichierTelecharge) -> dict[str, int]:
    """Analyse un ZIP déjà présent dans la zone d'atterrissage et le charge dans raw."""
    contenu = analyser_zip(fichier.chemin)
    return charger_jour(connexion, jour, contenu, fichier)


def ingerer_jour(
    jour: date,
    connexion: Any,
    dossier: Path,
    url_base: str = URL_BASE_PAR_DEFAUT,
    forcer_telechargement: bool = False,
    session: Any = None,
) -> dict[str, Any]:
    """Ingère le fichier d'un jour et renvoie des statistiques sur l'exécution.

    ``session`` permet d'injecter un client HTTP (les tests n'appellent pas le réseau).
    """
    verifier_date_passee(jour)
    debut = time.perf_counter()
    fichier = telecharger_jour(
        jour, dossier, url_base, session=session, forcer=forcer_telechargement
    )
    comptes = charger_fichier(jour, connexion, fichier)
    statistiques = {
        "date_fichier": jour.isoformat(),
        "fichier": fichier.chemin.name,
        "taille_octets": fichier.taille_octets,
        "fichier_deja_present": fichier.deja_present,
        **comptes,
        "duree_s": round(time.perf_counter() - debut, 2),
    }
    journal.info("Ingestion terminée : %s", statistiques)
    return statistiques


def connexion_depuis_environnement() -> Any:
    import psycopg2

    return psycopg2.connect(
        host=os.environ.get("ENTREPOT_HOST", "localhost"),
        port=int(os.environ.get("ENTREPOT_PORT", "5433")),
        dbname=os.environ.get("ENTREPOT_DB", "entrepot"),
        user=os.environ.get("ENTREPOT_USER", "entrepot"),
        password=os.environ["ENTREPOT_PASSWORD"],
    )


def main(arguments: list[str] | None = None) -> None:
    analyseur = argparse.ArgumentParser(description="Ingère le fichier quotidien d'une date.")
    analyseur.add_argument("--date", required=True, type=date.fromisoformat, help="AAAA-MM-JJ")
    analyseur.add_argument(
        "--dossier", type=Path, default=Path(os.environ.get("DOSSIER_DONNEES", "data"))
    )
    analyseur.add_argument("--forcer", action="store_true", help="retélécharger le fichier")
    options = analyseur.parse_args(arguments)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    connexion = connexion_depuis_environnement()
    try:
        ingerer_jour(
            options.date,
            connexion,
            options.dossier,
            os.environ.get("SOURCE_URL_JOUR", URL_BASE_PAR_DEFAUT),
            options.forcer,
        )
    finally:
        connexion.close()


if __name__ == "__main__":
    main()
