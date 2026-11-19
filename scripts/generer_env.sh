#!/usr/bin/env bash
# Crée .env à partir de .env.example en générant tous les secrets locaux.
# Ne remplace jamais un .env existant.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
    echo ".env existe déjà : rien n'est modifié." >&2
    exit 1
fi

# Premier interpréteur Python qui s'exécute vraiment : sous Windows, « python3 » peut
# n'être qu'un raccourci vers le Microsoft Store.
PYTHON=""
for candidat in python3 python py; do
    if "$candidat" -c "import secrets" >/dev/null 2>&1; then
        PYTHON=$candidat
        break
    fi
done
if [[ -z "$PYTHON" ]]; then
    echo "Python 3 introuvable." >&2
    exit 1
fi

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
