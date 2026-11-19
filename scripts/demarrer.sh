#!/usr/bin/env bash
# Lance la stack après avoir vérifié la mémoire, puis attend que tous les services soient sains.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    echo "Pas de .env : lancer d'abord bash scripts/generer_env.sh" >&2
    exit 1
fi

bash scripts/verifier_memoire.sh

docker compose up -d --build --wait --wait-timeout 300

port_airflow=$(grep -E '^AIRFLOW_HOST_PORT=' .env | cut -d= -f2)
port_metabase=$(grep -E '^METABASE_HOST_PORT=' .env | cut -d= -f2)
echo
docker compose ps --format 'table {{.Name}}\t{{.Status}}'
echo
echo "Airflow  : http://localhost:${port_airflow:-8082}"
echo "Metabase : http://localhost:${port_metabase:-3002}"
