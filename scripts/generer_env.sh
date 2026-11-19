#!/usr/bin/env bash
# Crée .env à partir de .env.example en générant tous les secrets locaux.
# Ne remplace jamais un .env existant.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
    echo ".env existe déjà : rien n'est modifié." >&2
    exit 1
fi

# Python est disponible sous Windows (py) comme sous Linux (python3).
PYTHON=$(command -v python3 || command -v python || command -v py)

secret() { "$PYTHON" -c "import secrets; print(secrets.token_urlsafe(24))"; }
fernet=$("$PYTHON" -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
jwt=$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(48))")

sed -e "s|^POSTGRES_PASSWORD=$|POSTGRES_PASSWORD=$(secret)|" \
    -e "s|^AIRFLOW_DB_PASSWORD=$|AIRFLOW_DB_PASSWORD=$(secret)|" \
    -e "s|^ENTREPOT_PASSWORD=$|ENTREPOT_PASSWORD=$(secret)|" \
    -e "s|^LECTEUR_PASSWORD=$|LECTEUR_PASSWORD=$(secret)|" \
    -e "s|^METABASE_DB_PASSWORD=$|METABASE_DB_PASSWORD=$(secret)|" \
    -e "s|^AIRFLOW_FERNET_KEY=$|AIRFLOW_FERNET_KEY=${fernet}|" \
    -e "s|^AIRFLOW_JWT_SECRET=$|AIRFLOW_JWT_SECRET=${jwt}|" \
    .env.example > .env

echo ".env créé avec des secrets générés."
