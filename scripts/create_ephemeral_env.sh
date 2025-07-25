#!/usr/bin/env bash
# scripts/create_ephemeral_env.sh
set -euo pipefail

# ------------------------------------------------------------
# Variables
# ------------------------------------------------------------
PROJECT_NAME="${1:-$(git rev-parse --abbrev-ref HEAD | tr '/' '-')}"
COMPOSE_FILE="docker-compose.ephemeral.yml"
ENV_FILE=".env.ephemeral"
REPO_DIR="$(git rev-parse --show-toplevel)"

# ------------------------------------------------------------
# Nettoyage si déjà existant
# ------------------------------------------------------------
echo "🧹 Nettoyage de l'environnement précédent : ${PROJECT_NAME}"
docker compose -p "${PROJECT_NAME}" -f "${REPO_DIR}/${COMPOSE_FILE}" down --remove-orphans --volumes || true

# ------------------------------------------------------------
# Génération du .env éphémère
# ------------------------------------------------------------
echo "🔐 Génération du .env éphémère"
cat > "${REPO_DIR}/${ENV_FILE}" <<EOF
COMPOSE_PROJECT_NAME=${PROJECT_NAME}
REDIS_URL=redis://redis:6379
OLLAMA_URL=http://ollama:11434
ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
EOF

# ------------------------------------------------------------
# Lancement de l'environnement
# ------------------------------------------------------------
echo "🚀 Lancement de l'environnement : ${PROJECT_NAME}"
docker compose -p "${PROJECT_NAME}" -f "${REPO_DIR}/${COMPOSE_FILE}" --env-file "${REPO_DIR}/${ENV_FILE}" up -d --build

# ------------------------------------------------------------
# Attente de santé
# ------------------------------------------------------------
echo "⏳ Attente de la santé des services…"
timeout=120
until curl -sf http://localhost:8000/health > /dev/null; do
    timeout=$((timeout - 5))
    if [ $timeout -le 0 ]; then
        echo "❌ Timeout : l'environnement n'a pas démarré correctement"
        docker compose -p "${PROJECT_NAME}" -f "${REPO_DIR}/${COMPOSE_FILE}" logs
        exit 1
    fi
    sleep 5
done

echo "✅ Environnement éphémère prêt !"
echo "   Nom du projet : ${PROJECT_NAME}"
echo "   API disponible : http://localhost:8000"
echo "   Logs : docker compose -p ${PROJECT_NAME} -f ${COMPOSE_FILE} logs -f"