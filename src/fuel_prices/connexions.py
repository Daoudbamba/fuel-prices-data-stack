"""Connexion psycopg2 à l'entrepôt à partir d'une connexion déclarée dans Airflow.

Le PostgresHook du fournisseur Airflow 7.x renvoie une connexion psycopg 3 quand ce
pilote est installé ; le chargement (COPY via copy_expert) et ses tests utilisent
psycopg2. On lit donc les paramètres de la connexion Airflow et on ouvre soi-même
une connexion psycopg2. Airflow n'est importé qu'à l'appel : le reste du paquet
s'utilise et se teste sans lui.
"""

from __future__ import annotations

from typing import Any


def connexion_depuis_airflow(id_connexion: str) -> Any:
    import psycopg2
    from airflow.sdk import BaseHook

    parametres = BaseHook.get_connection(id_connexion)
    return psycopg2.connect(
        host=parametres.host,
        port=parametres.port,
        dbname=parametres.schema,
        user=parametres.login,
        password=parametres.password,
    )
