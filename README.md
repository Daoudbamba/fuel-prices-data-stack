# Prix des carburants en France : une stack data batch avec dbt

> Projet en cours de construction. Le README complet (problématique, architecture,
> modèles dbt, tests, résultats chiffrés) arrive à la dernière étape.

Ingestion quotidienne du flux officiel prix-carburants.gouv.fr avec Airflow,
entrepôt PostgreSQL, transformations et tests de qualité avec dbt, tableau de bord Metabase.

## Démarrage rapide

Prérequis : Docker Desktop, Git Bash.

```bash
bash scripts/generer_env.sh
```

```bash
bash scripts/demarrer.sh
```

- Airflow : http://localhost:8082
- Metabase : http://localhost:3002

```bash
bash scripts/arreter.sh
```
