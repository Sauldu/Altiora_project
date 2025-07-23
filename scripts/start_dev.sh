# scripts/start_dev.sh

echo "🚀 Démarrage Altiora avec structure refactorisée"
# Lancer les services dans l'ordre
docker-compose up -d redis ollama
docker-compose up dash prometheus
docker-compose up -d doctoplus-ocr alm-connector excel-processor playwright-runner
# Attendre la santé des services
./scripts/validate_microservices.sh