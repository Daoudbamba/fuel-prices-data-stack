"""Téléchargement du fichier quotidien des prix des carburants.

La source publie un ZIP par jour à l'adresse ``<url_base>/AAAAMMJJ``, vers 23 h 25 le
jour même, et en garde environ un mois. Piège : pour une date absente (trop ancienne,
ou jour pas encore publié), elle répond HTTP 200 avec une page HTML au lieu d'un 404.
On vérifie donc la signature ZIP du contenu, pas seulement le code HTTP.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

journal = logging.getLogger(__name__)

URL_BASE_PAR_DEFAUT = "https://donnees.roulez-eco.fr/opendata/jour"
SIGNATURE_ZIP = b"PK\x03\x04"
DELAI_RESEAU_S = 60


class SourceIndisponibleError(RuntimeError):
    """Le fichier du jour demandé n'est pas (ou plus) publié par la source."""


@dataclass(frozen=True)
class FichierTelecharge:
    """Fichier ZIP présent dans la zone d'atterrissage."""

    chemin: Path
    sha256: str
    taille_octets: int
    deja_present: bool


def nom_fichier(jour: date) -> str:
    return f"PrixCarburants_quotidien_{jour:%Y%m%d}.zip"


def chemin_atterrissage(dossier: Path, jour: date) -> Path:
    """Chemin partitionné par année et mois, comme le serait une clé S3."""
    return dossier / f"annee={jour:%Y}" / f"mois={jour:%m}" / nom_fichier(jour)


def est_un_zip(contenu: bytes) -> bool:
    return contenu.startswith(SIGNATURE_ZIP)


def creer_session() -> requests.Session:
    """Session HTTP qui réessaie sur les erreurs serveur transitoires."""
    session = requests.Session()
    reessais = Retry(
        total=4,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=reessais))
    session.headers["User-Agent"] = "fuel-prices-data-stack/0.1"
    return session


def _empreinte(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def telecharger_jour(
    jour: date,
    dossier: Path,
    url_base: str = URL_BASE_PAR_DEFAUT,
    session: requests.Session | None = None,
    forcer: bool = False,
) -> FichierTelecharge:
    """Télécharge le ZIP du jour dans la zone d'atterrissage et renvoie son chemin.

    Idempotent : un fichier déjà présent et valide est réutilisé, sauf si ``forcer``.
    L'écriture passe par un fichier temporaire renommé à la fin, pour ne jamais laisser
    un ZIP tronqué en place si le téléchargement est interrompu.
    """
    cible = chemin_atterrissage(dossier, jour)

    if cible.exists() and not forcer:
        contenu = cible.read_bytes()
        if est_un_zip(contenu):
            journal.info("Fichier déjà présent, réutilisé : %s", cible)
            return FichierTelecharge(cible, _empreinte(contenu), len(contenu), deja_present=True)
        journal.warning("Fichier présent mais invalide, nouveau téléchargement : %s", cible)

    url = f"{url_base.rstrip('/')}/{jour:%Y%m%d}"
    session = session or creer_session()
    journal.info("Téléchargement de %s", url)
    reponse = session.get(url, timeout=DELAI_RESEAU_S)
    reponse.raise_for_status()
    contenu = reponse.content

    if not est_un_zip(contenu):
        type_contenu = reponse.headers.get("Content-Type", "inconnu")
        raise SourceIndisponibleError(
            f"Pas de fichier pour le {jour:%d/%m/%Y} (réponse {type_contenu}, "
            f"{len(contenu)} octets). La source ne garde qu'environ un mois d'historique "
            "et publie le fichier du jour vers 23 h 25."
        )

    cible.parent.mkdir(parents=True, exist_ok=True)
    temporaire = cible.with_suffix(".zip.part")
    temporaire.write_bytes(contenu)
    temporaire.replace(cible)
    journal.info("Fichier enregistré : %s (%d octets)", cible, len(contenu))
    return FichierTelecharge(cible, _empreinte(contenu), len(contenu), deja_present=False)
