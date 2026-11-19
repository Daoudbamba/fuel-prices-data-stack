#!/usr/bin/env bash
# Vérifie la mémoire disponible dans la VM Docker avant de lancer la stack.
# La VM n'a que 7,7 Go : quand d'autres projets tournent, elle peut se bloquer faute
# de mémoire. Le script lit /proc/meminfo et /proc/pressure/memory de la VM via un
# conteneur jetable, liste les conteneurs déjà lancés et refuse de continuer sous le seuil.
# Contourner (à vos risques) : FORCER=1 bash scripts/verifier_memoire.sh
set -euo pipefail
cd "$(dirname "$0")/.."

seuil_mo=3000
if [[ -f .env ]]; then
    valeur=$(grep -E '^MEMOIRE_MIN_DISPONIBLE_MO=' .env | cut -d= -f2 || true)
    seuil_mo=${valeur:-$seuil_mo}
fi

if ! docker info >/dev/null 2>&1; then
    echo "Docker ne répond pas : démarrer Docker Desktop d'abord." >&2
    exit 1
fi

# MSYS_NO_PATHCONV évite que Git Bash réécrive les chemins /proc en chemins Windows.
mesure=$(MSYS_NO_PATHCONV=1 docker run --rm alpine:3.22 sh -c \
    "grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo; head -2 /proc/pressure/memory")

total_mo=$(awk '/^MemTotal/ {print int($2/1024)}' <<<"$mesure")
dispo_mo=$(awk '/^MemAvailable/ {print int($2/1024)}' <<<"$mesure")
swap_utilise_mo=$(awk '/^SwapTotal/ {t=$2} /^SwapFree/ {f=$2} END {print int((t-f)/1024)}' <<<"$mesure")
pression=$(awk '/^some/ {print $2}' <<<"$mesure")

echo "VM Docker : ${dispo_mo} Mo disponibles sur ${total_mo} Mo, swap utilisé ${swap_utilise_mo} Mo, pression mémoire ${pression}"
echo "Conteneurs en cours d'exécution :"
docker stats --no-stream --format '  {{.Name}}\t{{.MemUsage}}' || true

if (( dispo_mo < seuil_mo )); then
    echo "Moins de ${seuil_mo} Mo disponibles : arrêter d'autres stacks avant de lancer celle-ci." >&2
    if [[ "${FORCER:-0}" != "1" ]]; then
        exit 2
    fi
    echo "FORCER=1 : on continue malgré tout." >&2
fi
