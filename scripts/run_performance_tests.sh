#!/bin/bash
# scripts/run_performance_tests.sh

set -e

echo "🚀 Tests de Performance Altiora"
echo "==============================="

# Configuration
REDIS_URL="redis://localhost:6379"
OLLAMA_HOST="http://localhost:11434"
MAX_CPU=85
MAX_MEMORY=25

# Vérifier les services
echo "📋 Vérification des services..."
if ! curl -s $OLLAMA_HOST/health &>/dev/null; then
    echo "❌ Ollama non accessible"
    exit 1
fi

if ! redis-cli ping &>/dev/null; then
    echo "❌ Redis non accessible"
    exit 1
fi

# Lancer les tests
echo "🔥 Lancement des tests de charge..."

# Test 1: Charge légère
echo "📊 Test 1: Charge légère (5 concurrents)"
pytest tests/performance/test_load_testing.py::test_cpu_load_pipeline -v -s \
    --performance-concurrent=5 --performance-duration=60

# Test 2: Charge moyenne
echo "📊 Test 2: Charge moyenne (15 concurrents)"
pytest tests/performance/test_load_testing.py::test_cpu_load_pipeline -v -s \
    --performance-concurrent=15 --performance-duration=120

# Test 3: Charge lourde
echo "📊 Test 3: Charge lourde (30 concurrents)"
pytest tests/performance/test_load_testing.py::test_cpu_load_pipeline -v -s \
    --performance-concurrent=30 --performance-duration=300

# Générer le rapport
echo "📈 Génération du rapport de performance..."
python scripts/generate_performance_report.py

echo "✅ Tests de performance terminés!"
echo "📋 Rapport disponible dans: reports/performance_report.html"