#!/usr/bin/env bash
# Démonstration : une donnée cassée volontairement est arrêtée par un test dbt.
#
#   1. On multiplie par 10 un vrai prix de gazole du dernier jour dans raw.prix
#      (la virgule décalée : 2,086 € devient 20,86 €).
#   2. dbt build : le test métier prix_dans_les_bornes échoue, et dbt ne reconstruit
#      pas les marts qui en dépendent. Le tableau de bord garde les derniers bons chiffres.
#   3. Correction : on rejoue l'ingestion de la date. Le chargement étant idempotent,
#      raw retrouve les valeurs du fichier officiel et dbt build repasse.
#
# Prérequis : la stack tourne (bash scripts/demarrer.sh) et au moins un jour est ingéré.
set -euo pipefail
cd "$(dirname "$0")/.."

export MSYS_NO_PATHCONV=1
mot_de_passe=$(grep -E '^ENTREPOT_PASSWORD=' .env | cut -d= -f2)

sql() {
    docker exec -e PGPASSWORD="$mot_de_passe" fuel-postgres \
        psql -h localhost -U entrepot -d entrepot -v ON_ERROR_STOP=1 "$@"
}
dbt() {
    docker exec -w /opt/airflow/dbt fuel-airflow-scheduler bash -c "\"\$DBT_BIN\" $*"
}

titre() { printf '\n===== %s =====\n' "$1"; }

titre "1. Donnée cassée : un prix de gazole multiplié par 10 dans raw.prix"
cible=$(sql -tAc "
    select date_fichier || '|' || id_station
    from raw.prix
    where date_fichier = (select max(date_fichier) from raw.journal_ingestion)
      and carburant = 'Gazole'
      and maj::timestamp::date >= date_fichier - 1
    order by id_station
    limit 1")
jour=${cible%%|*}
station=${cible##*|}
sql -c "
    update raw.prix
    set valeur = (valeur::numeric * 10)::text
    where date_fichier = '$jour' and id_station = '$station' and carburant = 'Gazole'
    returning date_fichier, id_station, carburant, valeur as valeur_cassee"

titre "2. dbt build : le test métier doit échouer et bloquer les marts"
set +e
dbt build 2>&1 | grep -E "prix_dans_les_bornes|SKIP|Done\. PASS" | sed 's/\x1b\[[0-9;]*m//g'
set -e
titre "Lignes fautives conservées par dbt dans le schéma audit"
sql -c "
    select date_fichier, id_station, code_carburant, prix_litre,
           prix_min_plausible, prix_max_plausible
    from audit.echecs_prix_hors_bornes"

titre "3. Correction : rejeu idempotent de l'ingestion du $jour"
docker exec fuel-airflow-scheduler python -m fuel_prices.ingestion --date "$jour" 2>&1 | tail -1
sql -c "
    select date_fichier, id_station, carburant, valeur as valeur_retablie
    from raw.prix
    where date_fichier = '$jour' and id_station = '$station' and carburant = 'Gazole'"

titre "4. dbt build après correction"
dbt build 2>&1 | grep -E "prix_dans_les_bornes|Done\. PASS" | sed 's/\x1b\[[0-9;]*m//g'
