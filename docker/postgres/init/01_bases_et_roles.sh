#!/usr/bin/env bash
# Exécuté une seule fois par l'image postgres, à la création du volume de données.
# Crée trois bases dans la même instance et un rôle par usage :
#   - airflow  : métadonnées d'Airflow ;
#   - entrepot : l'entrepôt (schémas raw, staging, intermediate, marts), écrit par
#                l'ingestion et par dbt ;
#   - metabase : base applicative de Metabase.
# Le rôle « lecteur » ne peut que lire l'entrepôt : c'est lui que Metabase utilise.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-SQL
    CREATE ROLE ${AIRFLOW_DB_USER} LOGIN PASSWORD '${AIRFLOW_DB_PASSWORD}';
    CREATE DATABASE airflow OWNER ${AIRFLOW_DB_USER};

    CREATE ROLE ${ENTREPOT_USER} LOGIN PASSWORD '${ENTREPOT_PASSWORD}';
    CREATE DATABASE ${ENTREPOT_DB} OWNER ${ENTREPOT_USER};

    CREATE ROLE ${LECTEUR_USER} LOGIN PASSWORD '${LECTEUR_PASSWORD}';

    CREATE ROLE ${METABASE_DB_USER} LOGIN PASSWORD '${METABASE_DB_PASSWORD}';
    CREATE DATABASE metabase OWNER ${METABASE_DB_USER};

    -- Par défaut, PostgreSQL autorise tout rôle à se connecter à toute base :
    -- chaque base n'accepte ici que son propriétaire.
    REVOKE CONNECT ON DATABASE airflow FROM PUBLIC;
    REVOKE CONNECT ON DATABASE metabase FROM PUBLIC;
SQL

# Les schémas appartiennent au rôle d'écriture. Les droits par défaut donnent au
# lecteur l'accès en lecture aux tables que dbt créera plus tard.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$ENTREPOT_DB" <<-SQL
    REVOKE ALL ON DATABASE ${ENTREPOT_DB} FROM PUBLIC;
    GRANT CONNECT ON DATABASE ${ENTREPOT_DB} TO ${LECTEUR_USER};
    REVOKE CREATE ON SCHEMA public FROM PUBLIC;

    CREATE SCHEMA raw AUTHORIZATION ${ENTREPOT_USER};
    CREATE SCHEMA staging AUTHORIZATION ${ENTREPOT_USER};
    CREATE SCHEMA intermediate AUTHORIZATION ${ENTREPOT_USER};
    CREATE SCHEMA marts AUTHORIZATION ${ENTREPOT_USER};

    -- Metabase ne voit que la couche exposée.
    GRANT USAGE ON SCHEMA marts TO ${LECTEUR_USER};
    ALTER DEFAULT PRIVILEGES FOR ROLE ${ENTREPOT_USER} IN SCHEMA marts
        GRANT SELECT ON TABLES TO ${LECTEUR_USER};
SQL

echo "Bases airflow, ${ENTREPOT_DB} et metabase créées."
