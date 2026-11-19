# Image Airflow du projet : Airflow 3.3.2 (Python 3.12), fournisseur PostgreSQL,
# et dbt installé dans un environnement virtuel séparé.
ARG AIRFLOW_VERSION=3.3.2
FROM apache/airflow:slim-${AIRFLOW_VERSION}-python3.12

ARG AIRFLOW_VERSION=3.3.2

# curl sert aux sondes de santé des conteneurs.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
USER airflow

# L'image slim n'a aucun pilote de base de données : le fournisseur PostgreSQL apporte
# psycopg2. Sa version suit les contraintes officielles d'Airflow.
RUN pip install --no-cache-dir \
        --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt" \
        apache-airflow-providers-postgres

COPY requirements/dbt.txt /tmp/requirements/dbt.txt
RUN python -m venv /home/airflow/dbt-venv \
    && /home/airflow/dbt-venv/bin/pip install --no-cache-dir -r /tmp/requirements/dbt.txt

# Le code d'ingestion (src/) et le projet dbt (dbt/) sont montés en volume par Compose.
ENV PYTHONPATH=/opt/airflow/src \
    DBT_BIN=/home/airflow/dbt-venv/bin/dbt \
    DBT_PROJECT_DIR=/opt/airflow/dbt \
    DBT_PROFILES_DIR=/opt/airflow/dbt
