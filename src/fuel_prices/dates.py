"""Choix de la date de fichier à ingérer pour une exécution du DAG.

Le fichier du jour J est publié vers 23 h 25 (heure de Paris) le jour J. Le DAG tourne
chaque matin à 6 h : l'exécution du jour J+1 ingère donc le fichier de la veille, J.

Avec la planification par défaut d'Airflow 3 (CronTriggerTimetable), la date logique
d'une exécution est son heure de déclenchement. On en déduit la date à ingérer, sauf si
l'exécution impose une date (paramètre ``date_fichier``, pour rejouer un jour précis).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

FUSEAU_SOURCE = ZoneInfo("Europe/Paris")
# La source garde environ un mois de fichiers (mesuré en novembre 2026) ; on garde une marge.
RETENTION_SOURCE_JOURS = 35


def date_a_ingerer(date_logique: datetime, date_imposee: str | None = None) -> date:
    """Date du fichier à ingérer : celle imposée, sinon la veille de la date logique."""
    if date_imposee:
        return date.fromisoformat(date_imposee)
    if date_logique.tzinfo is None:
        raise ValueError("La date logique doit porter un fuseau horaire.")
    return date_logique.astimezone(FUSEAU_SOURCE).date() - timedelta(days=1)


def est_hors_retention(jour: date, aujourd_hui: date) -> bool:
    """Vrai si la source ne peut plus fournir ce jour : inutile de réessayer."""
    return (aujourd_hui - jour).days > RETENTION_SOURCE_JOURS
