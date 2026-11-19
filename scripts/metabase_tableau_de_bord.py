"""Crée (ou recrée) le tableau de bord Metabase « Prix des carburants » par l'API.

Le tableau de bord est du code : une installation neuve le retrouve à l'identique, et
ses requêtes SQL sont relues comme le reste du projet. Le script est idempotent : il
archive la version précédente de la collection avant de la recréer.

Étapes :
  1. création du compte administrateur au premier lancement (identifiants du .env) ;
  2. connexion de Metabase à l'entrepôt avec le rôle « lecteur » (schéma marts seul) ;
  3. questions SQL et tableau de bord, avec un filtre « Carburant » commun ;
  4. option --public : lien public en lecture seule, utile pour une capture d'écran.

Usage (stack lancée) :
    .venv/Scripts/python scripts/metabase_tableau_de_bord.py [--public]
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import requests

RACINE = Path(__file__).resolve().parent.parent
NOM_BASE = "Entrepôt prix des carburants"
NOM_COLLECTION = "Prix des carburants"
NOM_TABLEAU = "Prix des carburants en France"
LARGEUR_GRILLE = 24


def lire_env(chemin: Path) -> dict[str, str]:
    valeurs = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            valeurs[cle.strip()] = valeur.strip()
    return valeurs


class Metabase:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")
        self.session = requests.Session()

    def appel(self, methode: str, chemin: str, **kwargs: Any) -> Any:
        reponse = self.session.request(methode, f"{self.url}/api/{chemin}", timeout=60, **kwargs)
        if reponse.status_code >= 400:
            raise RuntimeError(
                f"{methode} {chemin} : HTTP {reponse.status_code} {reponse.text[:300]}"
            )
        return reponse.json() if reponse.content else None

    def attendre(self) -> None:
        for _ in range(60):
            try:
                if self.appel("GET", "health").get("status") == "ok":
                    return
            except (requests.RequestException, RuntimeError):
                pass
            time.sleep(5)
        raise RuntimeError("Metabase ne répond pas.")

    def se_connecter(self, env: dict[str, str]) -> None:
        proprietes = self.appel("GET", "session/properties")
        identifiants = {
            "email": env["METABASE_ADMIN_EMAIL"],
            "password": env["METABASE_ADMIN_PASSWORD"],
        }
        if not proprietes.get("has-user-setup"):
            print("Premier lancement : création du compte administrateur.")
            self.appel(
                "POST",
                "setup",
                json={
                    "token": proprietes["setup-token"],
                    "user": {**identifiants, "first_name": "Admin", "last_name": "Fuel"},
                    "prefs": {"site_name": "Prix des carburants", "site_locale": "fr"},
                },
            )
        session = self.appel(
            "POST",
            "session",
            json={"username": identifiants["email"], "password": identifiants["password"]},
        )
        self.session.headers["X-Metabase-Session"] = session["id"]


def base_entrepot(mb: Metabase, env: dict[str, str]) -> int:
    """Connexion à l'entrepôt avec le rôle en lecture seule, limitée au schéma marts."""
    for base in mb.appel("GET", "database")["data"]:
        if base["name"] == NOM_BASE:
            identifiant = base["id"]
            break
    else:
        print("Connexion de Metabase à l'entrepôt (rôle lecteur).")
        identifiant = mb.appel(
            "POST",
            "database",
            json={
                "engine": "postgres",
                "name": NOM_BASE,
                "details": {
                    "host": "postgres",
                    "port": 5432,
                    "dbname": env.get("ENTREPOT_DB", "entrepot"),
                    "user": env.get("LECTEUR_USER", "lecteur"),
                    "password": env["LECTEUR_PASSWORD"],
                    "schema-filters-type": "inclusion",
                    "schema-filters-patterns": "marts",
                    "ssl": False,
                },
            },
        )["id"]
    mb.appel("POST", f"database/{identifiant}/sync_schema")
    return identifiant


def formats_francais(mb: Metabase) -> None:
    """Virgule décimale, espace pour les milliers, dates « 18 novembre 2026 »."""
    mb.appel(
        "PUT",
        "setting/custom-formatting",
        json={
            "value": {
                "type/Number": {"number_separators": ", "},
                "type/Temporal": {"date_style": "D MMMM, YYYY", "time_style": "HH:mm"},
            }
        },
    )


def collection_neuve(mb: Metabase) -> int:
    """Archive la collection précédente (et son contenu) puis en crée une vide."""
    for collection in mb.appel("GET", "collection"):
        if collection.get("name") == NOM_COLLECTION and not collection.get("archived"):
            mb.appel("PUT", f"collection/{collection['id']}", json={"archived": True})
    return mb.appel(
        "POST",
        "collection",
        json={
            "name": NOM_COLLECTION,
            "description": "Tableau de bord du projet fuel-prices-data-stack",
        },
    )["id"]


def balise_carburant() -> dict[str, Any]:
    return {
        "carburant": {
            "id": str(uuid.uuid4()),
            "name": "carburant",
            "display-name": "Carburant",
            "type": "text",
            "default": "Gazole",
            "required": True,
        }
    }


# --- Questions SQL ---------------------------------------------------------------------
# Les comparaisons régionales et par enseigne sont en écart à la moyenne nationale
# (centimes par litre) : sur un axe partant de zéro, des prix de 2,08 € et 2,20 €
# paraîtraient identiques ; l'écart se lit directement sans tronquer l'axe.

DERNIER_JOUR = "(select max(date_fichier) from marts.mart_prix_regions_quotidiens)"

# Metabase peut regrouper des barres dans « Other » en ADDITIONNANT leurs valeurs, ce qui
# serait trompeur pour des écarts : réglage désactivé, et cartes assez hautes (DISPOSITION).
SANS_REGROUPEMENT = {"graph.max_categories_enabled": False, "graph.max_categories": 50}

QUESTIONS: list[dict[str, Any]] = [
    {
        "cle": "kpi_prix",
        "nom": "Prix moyen national",
        "display": "smartscalar",
        "filtre": True,
        "sql": """
select date_fichier as "Jour", prix_moyen as "Prix moyen (€/L)"
from marts.mart_prix_regions_quotidiens
where est_national and code_carburant = {{carburant}}
order by date_fichier""",
        "visualisation": {
            "scalar.decimals": 3,
            "scalar.suffix": " €",
            "column_settings": {'["name","Prix moyen (€/L)"]': {"decimals": 3}},
        },
    },
    {
        "cle": "kpi_stations",
        "nom": "Stations avec un prix récent",
        "display": "scalar",
        "filtre": True,
        "sql": f"""
select nb_stations as "Stations"
from marts.mart_prix_regions_quotidiens
where est_national and code_carburant = {{{{carburant}}}}
  and date_fichier = {DERNIER_JOUR}""",
        "visualisation": {},
    },
    {
        "cle": "kpi_ecart_types",
        "nom": "Écart pétroliers − grande distribution",
        "display": "scalar",
        "filtre": True,
        "sql": """
select round(100 * (
    max(prix_moyen) filter (where type_enseigne = 'petrolier')
  - max(prix_moyen) filter (where type_enseigne = 'grande_distribution')
), 1) as "Centimes par litre"
from marts.mart_prix_enseignes_quotidiens
where niveau = 'type_enseigne' and code_carburant = {{carburant}}
  and date_fichier = (select max(date_fichier) from marts.mart_prix_enseignes_quotidiens)""",
        "visualisation": {"scalar.suffix": " c€/L"},
    },
    {
        "cle": "evolution",
        "nom": "Évolution du prix moyen national, par carburant",
        "display": "line",
        "filtre": False,
        "sql": """
select date_fichier as "Jour", libelle_carburant as "Carburant", prix_moyen as "Prix moyen (€/L)"
from marts.mart_prix_regions_quotidiens
where est_national
order by 1, 2""",
        "visualisation": {
            "graph.dimensions": ["Jour", "Carburant"],
            "graph.metrics": ["Prix moyen (€/L)"],
            "graph.y_axis.title_text": "€ par litre",
            "graph.x_axis.title_text": "Date du fichier",
            "line.marker_enabled": False,
        },
    },
    {
        "cle": "types_enseigne",
        "nom": "Grande distribution, pétroliers, indépendants : évolution",
        "display": "line",
        "filtre": True,
        "sql": """
select date_fichier as "Jour",
       case type_enseigne
           when 'grande_distribution' then 'Grande distribution'
           when 'petrolier' then 'Pétroliers'
           when 'independant' then 'Indépendants'
           when 'inconnu' then 'Enseigne inconnue'
           else 'Autres enseignes'
       end as "Type d'enseigne",
       prix_moyen as "Prix moyen (€/L)"
from marts.mart_prix_enseignes_quotidiens
where niveau = 'type_enseigne' and code_carburant = {{carburant}}
  and type_enseigne in ('grande_distribution', 'petrolier', 'independant')
order by 1, 2""",
        "visualisation": {
            "graph.dimensions": ["Jour", "Type d'enseigne"],
            "graph.metrics": ["Prix moyen (€/L)"],
            "graph.y_axis.title_text": "€ par litre",
            "line.marker_enabled": False,
        },
    },
    {
        "cle": "regions",
        "nom": "Écart à la moyenne nationale par région (dernier jour)",
        "display": "row",
        "filtre": True,
        "sql": f"""
with jour as (
    select * from marts.mart_prix_regions_quotidiens
    where code_carburant = {{{{carburant}}}} and date_fichier = {DERNIER_JOUR}
)
select r.nom_region as "Région",
       round(100 * (r.prix_moyen - n.prix_moyen), 1) as "Écart (centimes/L)"
from jour r
cross join (select prix_moyen from jour where est_national) n
where not r.est_national
order by 2""",
        "visualisation": {
            "graph.dimensions": ["Région"],
            "graph.metrics": ["Écart (centimes/L)"],
            "graph.show_values": True,
            **SANS_REGROUPEMENT,
        },
    },
    {
        "cle": "enseignes",
        "nom": "Écart à la moyenne nationale par enseigne (dernier jour)",
        "display": "row",
        "filtre": True,
        "sql": """
with jour as (
    select * from marts.mart_prix_enseignes_quotidiens
    where code_carburant = {{carburant}}
      and date_fichier = (select max(date_fichier) from marts.mart_prix_enseignes_quotidiens)
),
national as (
    select prix_moyen from marts.mart_prix_regions_quotidiens
    where est_national and code_carburant = {{carburant}}
      and date_fichier = (select max(date_fichier) from jour)
)
select e.enseigne || ' (' || e.nb_stations || ')' as "Enseigne (stations)",
       round(100 * (e.prix_moyen - n.prix_moyen), 1) as "Écart (centimes/L)"
from jour e
cross join national n
where e.niveau = 'enseigne' and e.enseigne not in ('Inconnue', 'Autre')
order by 2""",
        "visualisation": {
            "graph.dimensions": ["Enseigne (stations)"],
            "graph.metrics": ["Écart (centimes/L)"],
            "graph.show_values": True,
            **SANS_REGROUPEMENT,
        },
    },
    {
        "cle": "moins_cheres",
        "nom": "Les 20 stations les moins chères de France (dernier jour)",
        "display": "table",
        "filtre": True,
        "sql": """
select rang_national as "Rang", prix_litre as "Prix (€/L)", enseigne as "Enseigne",
       ville as "Ville", nom_departement as "Département", adresse as "Adresse",
       to_char(maj at time zone 'Europe/Paris', 'DD/MM HH24:MI') as "Mis à jour"
from marts.mart_classement_stations
where code_carburant = {{carburant}} and rang_national <= 20
order by rang_national, prix_litre""",
        "visualisation": {"column_settings": {'["name","Prix (€/L)"]': {"decimals": 3}}},
    },
]

# Disposition sur la grille de 24 colonnes : (clé, ligne, colonne, largeur, hauteur).
DISPOSITION = [
    ("kpi_prix", 4, 0, 8, 4),
    ("kpi_stations", 4, 8, 8, 4),
    ("kpi_ecart_types", 4, 16, 8, 4),
    ("evolution", 8, 0, 12, 8),
    ("types_enseigne", 8, 12, 12, 8),
    # Hauteur 13 : le graphique en barres horizontales regroupe dans « Other » les barres
    # qui ne tiennent pas dans la carte ; les 18 enseignes doivent toutes s'afficher.
    ("regions", 16, 0, 12, 13),
    ("enseignes", 16, 12, 12, 13),
    ("moins_cheres", 29, 0, 24, 10),
]

TEXTE_INTRODUCTION = (
    "## Prix des carburants en France\n"
    "Flux officiel quotidien **prix-carburants.gouv.fr** (≈ 9 950 stations), ingéré chaque "
    "matin par Airflow et transformé par dbt. Seuls les prix mis à jour depuis 7 jours au plus "
    "et proches de la médiane départementale entrent dans les moyennes.  \n"
    "Enseignes : © contributeurs **OpenStreetMap**, licence ODbL."
)


def creer_tableau(mb: Metabase, base: int, collection: int) -> int:
    cartes: dict[str, int] = {}
    for question in QUESTIONS:
        requete: dict[str, Any] = {"query": question["sql"].strip()}
        if question["filtre"]:
            requete["template-tags"] = balise_carburant()
        carte = mb.appel(
            "POST",
            "card",
            json={
                "name": question["nom"],
                "display": question["display"],
                "collection_id": collection,
                "visualization_settings": question["visualisation"],
                "dataset_query": {"database": base, "type": "native", "native": requete},
            },
        )
        cartes[question["cle"]] = carte["id"]
        print(f"  question créée : {question['nom']}")

    tableau = mb.appel("POST", "dashboard", json={"name": NOM_TABLEAU, "collection_id": collection})
    parametre = {
        "id": "carburant",
        "name": "Carburant",
        "slug": "carburant",
        "type": "string/=",
        "sectionId": "string",
        "default": ["Gazole"],
        "values_query_type": "list",
        "values_source_type": "static-list",
        "values_source_config": {"values": ["Gazole", "E10", "SP98", "SP95", "E85", "GPLc"]},
    }
    avec_filtre = {q["cle"] for q in QUESTIONS if q["filtre"]}
    cartes_tableau: list[dict[str, Any]] = [
        {
            "id": -1,
            "card_id": None,
            "row": 0,
            "col": 0,
            "size_x": LARGEUR_GRILLE,
            # Assez haut pour que l'attribution OpenStreetMap (exigée par l'ODbL) reste visible.
            "size_y": 4,
            "visualization_settings": {
                "virtual_card": {
                    "name": None,
                    "display": "text",
                    "visualization_settings": {},
                    "dataset_query": {},
                    "archived": False,
                },
                "text": TEXTE_INTRODUCTION,
            },
        }
    ]
    for numero, (cle, ligne, colonne, largeur, hauteur) in enumerate(DISPOSITION, start=2):
        cartes_tableau.append(
            {
                "id": -numero,
                "card_id": cartes[cle],
                "row": ligne,
                "col": colonne,
                "size_x": largeur,
                "size_y": hauteur,
                "visualization_settings": {},
                "parameter_mappings": (
                    [
                        {
                            "parameter_id": "carburant",
                            "card_id": cartes[cle],
                            "target": ["variable", ["template-tag", "carburant"]],
                        }
                    ]
                    if cle in avec_filtre
                    else []
                ),
            }
        )
    mb.appel(
        "PUT",
        f"dashboard/{tableau['id']}",
        json={"parameters": [parametre], "dashcards": cartes_tableau},
    )
    return tableau["id"]


def verifier_cartes(mb: Metabase, tableau: int) -> None:
    """Exécute chaque question comme le ferait le tableau de bord et compte ses lignes."""
    detail = mb.appel("GET", f"dashboard/{tableau}")
    erreurs = 0
    for carte in detail["dashcards"]:
        if not carte.get("card_id"):
            continue
        resultat = mb.appel("POST", f"card/{carte['card_id']}/query", json={})
        nom = carte["card"]["name"]
        if resultat.get("status") != "completed":
            erreurs += 1
            print(f"  ÉCHEC  {nom} : {resultat.get('error', '')[:200]}")
        else:
            print(f"  ok     {nom} : {resultat['row_count']} ligne(s)")
    if erreurs:
        raise RuntimeError(f"{erreurs} question(s) en erreur.")


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyseur.add_argument("--public", action="store_true", help="créer un lien public")
    options = analyseur.parse_args()

    env = lire_env(RACINE / ".env")
    mb = Metabase(f"http://localhost:{env.get('METABASE_HOST_PORT', '3002')}")
    mb.attendre()
    mb.se_connecter(env)
    formats_francais(mb)
    base = base_entrepot(mb, env)
    collection = collection_neuve(mb)
    tableau = creer_tableau(mb, base, collection)
    print("Vérification des questions :")
    verifier_cartes(mb, tableau)
    print(f"Tableau de bord : {mb.url}/dashboard/{tableau}")

    if options.public:
        mb.appel("PUT", "setting/enable-public-sharing", json={"value": True})
        lien = mb.appel("POST", f"dashboard/{tableau}/public_link")
        print(f"Lien public (lecture seule) : {mb.url}/public/dashboard/{lien['uuid']}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as erreur:
        sys.exit(f"Erreur : {erreur}")
