#!/bin/bash
"""
Script de validation pour Docker Compose
Vérifie la configuration et l'état des services
"""

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🐳 Validation de la configuration Docker Compose"
echo "================================================"

# Fonction pour afficher les résultats
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
        ERRORS=$((ERRORS + 1))
    fi
}

# Fonction pour afficher les avertissements
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

ERRORS=0
WARNINGS=0

# 1. Vérifier la présence de Docker et Docker Compose
echo -e "\n1️⃣ Vérification des prérequis"

command -v docker >/dev/null 2>&1
print_result $? "Docker installé"

command -v docker-compose >/dev/null 2>&1 || command -v docker compose >/dev/null 2>&1
print_result $? "Docker Compose installé"

# 2. Valider la syntaxe du fichier
echo -e "\n2️⃣ Validation de la syntaxe"

docker-compose config >/dev/null 2>&1
print_result $? "Syntaxe docker-compose.yml valide"

# 3. Vérifier les images requises
echo -e "\n3️⃣ Vérification des images Docker"

IMAGES=(
    "ollama/ollama:latest"
    "redis:7-alpine"
    "mcr.microsoft.com/playwright/python:v1.40.0-focal"
)

for image in "${IMAGES[@]}"; do
    if docker image inspect "$image" >/dev/null 2>&1; then
        print_result 0 "Image $image disponible"
    else
        print_warning "Image $image non trouvée (sera téléchargée)"
    fi
done

# 4. Vérifier les volumes et réseaux
echo -e "\n4️⃣ Vérification des volumes et réseaux"

# Vérifier si le réseau existe
if docker network ls | grep -q "ai-network"; then
    print_result 0 "Réseau ai-network existe"
else
    print_warning "Réseau ai-network sera créé"
fi

# 5. Vérifier les ports disponibles
echo -e "\n5️⃣ Vérification des ports"

PORTS=(
    "11434:Ollama"
    "6379:Redis"
    "8001:OCR Service"
    "8002:ALM Service"
    "8003:Excel Service"
    "8004:Playwright Service"
    "8080:Web UI"
)

for port_info in "${PORTS[@]}"; do
    port="${port_info%%:*}"
    service="${port_info#*:}"
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port $port ($service) déjà utilisé"
    else
        print_result 0 "Port $port ($service) disponible"
    fi
done

# 6. Vérifier les fichiers Dockerfile
echo -e "\n6️⃣ Vérification des Dockerfiles"

DOCKERFILES=(
    "services/ocr/Dockerfile"
    "services/alm/Dockerfile"
    "services/excel/Dockerfile"
    "services/playwright/Dockerfile"
    "Dockerfile"
)

for dockerfile in "${DOCKERFILES[@]}"; do
    if [ -f "$dockerfile" ]; then
        print_result 0 "Dockerfile $dockerfile existe"
    else
        print_result 1 "Dockerfile $dockerfile manquant"
    fi
done

# 7. Vérifier la configuration des ressources
echo -e "\n7️⃣ Vérification des ressources système"

# Mémoire disponible
TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
if [ "$TOTAL_MEM" -ge 32 ]; then
    print_result 0 "Mémoire suffisante: ${TOTAL_MEM}GB"
else
    print_warning "Mémoire limitée: ${TOTAL_MEM}GB (32GB recommandés)"
fi

# CPU disponibles
CPU_COUNT=$(nproc)
if [ "$CPU_COUNT" -ge 8 ]; then
    print_result 0 "CPUs suffisants: $CPU_COUNT"
else
    print_warning "CPUs limités: $CPU_COUNT (8+ recommandés)"
fi

# 8. Vérifier les variables d'environnement requises
echo -e "\n8️⃣ Vérification des variables d'environnement"

if [ -f .env ]; then
    print_result 0 "Fichier .env présent"
    
    # Vérifier les variables critiques
    REQUIRED_VARS=(
        "OLLAMA_HOST"
        "REDIS_URL"
        "JWT_SECRET_KEY"
    )
    
    for var in "${REQUIRED_VARS[@]}"; do
        if grep -q "^$var=" .env; then
            print_result 0 "Variable $var définie"
        else
            print_result 1 "Variable $var manquante"
        fi
    done
else
    print_result 1 "Fichier .env manquant"
fi

# 9. Test de démarrage des services de base
echo -e "\n9️⃣ Test de démarrage (dry-run)"

if [ "$1" != "--skip-dry-run" ]; then
    echo "Tentative de démarrage des services de base..."
    
    # Démarrer uniquement Redis et Ollama pour test
    docker-compose up -d redis ollama 2>/dev/null
    
    sleep 5
    
    # Vérifier l'état
    if docker-compose ps | grep -q "redis.*Up"; then
        print_result 0 "Redis démarré avec succès"
        docker-compose stop redis >/dev/null 2>&1
    else
        print_result 1 "Redis n'a pas pu démarrer"
    fi
    
    if docker-compose ps | grep -q "ollama.*Up"; then
        print_result 0 "Ollama démarré avec succès"
        docker-compose stop ollama >/dev/null 2>&1
    else
        print_result 1 "Ollama n'a pas pu démarrer"
    fi
fi

# 10. Recommandations finales
echo -e "\n📊 Résumé de la validation"
echo "=========================="
echo -e "Erreurs: ${RED}$ERRORS${NC}"
echo -e "Avertissements: ${YELLOW}$WARNINGS${NC}"

if [ $ERRORS -eq 0 ]; then
    echo -e "\n${GREEN}✅ Configuration Docker Compose valide!${NC}"
    echo -e "\nPour démarrer les services:"
    echo "  - Services de base: docker-compose up -d"
    echo "  - Tous les services: docker-compose --profile full up -d"
    echo "  - Avec interface web: docker-compose --profile full --profile ui up -d"
else
    echo -e "\n${RED}❌ Des erreurs doivent être corrigées avant de continuer${NC}"
    exit 1
fi

# Créer un rapport de validation
echo -e "\n📝 Génération du rapport de validation..."
cat > docker-validation-report.txt << EOF
Docker Compose Validation Report
Generated: $(date)

Errors: $ERRORS
Warnings: $WARNINGS

System Information:
- Total Memory: ${TOTAL_MEM}GB
- CPU Count: $CPU_COUNT
- Docker Version: $(docker --version 2>/dev/null || echo "Not installed")
- Docker Compose Version: $(docker-compose --version 2>/dev/null || echo "Not installed")

Validation Complete
EOF

echo "Rapport sauvegardé dans docker-validation-report.txt"

