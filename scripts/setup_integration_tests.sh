#!/bin/bash
# scripts/setup_integration_tests.sh

echo "🔄 Configuration des tests d'intégration..."

# Vérifier Docker
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose non installé"
    exit 1
fi

# Lancer les services
echo "📦 Lancement des services Docker..."
docker-compose down
docker-compose up -d --build --wait

# Vérifier la santé des services
echo "🔍 Vérification des services..."
./scripts/validate_microservices.sh

# Préparer les modèles Ollama
echo "🤖 Vérification des modèles Ollama..."
if ! curl -s http://localhost:11434/api/tags | grep -q "qwen3"; then
    echo "📥 Téléchargement de qwen3:32b-q4_K_M..."
    ollama pull qwen3:32b-q4_K_M
fi

if ! curl -s http://localhost:11434/api/tags | grep -q "starcoder2"; then
    echo "📥 Téléchargement de starcoder2:15b-q8_0..."
    ollama pull starcoder2:15b-q8_0
fi

echo "✅ Environnement de test d'intégration prêt!"