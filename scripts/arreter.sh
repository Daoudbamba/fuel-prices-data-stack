#!/usr/bin/env bash
# Arrête la stack en gardant les volumes (entrepôt, métadonnées, fichiers téléchargés).
# Tout supprimer, données comprises : docker compose down --volumes
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose stop
