# Makefile
.PHONY: test-integration test-performance setup-integration

setup-integration:
	@echo "🚀 Configuration des tests d'intégration..."
	@docker-compose up -d --wait
	@./scripts/validate_microservices.sh

test-integration: setup-integration
	@echo "🧪 Lancement des tests d'intégration..."
	@pytest tests/integration/ -v --tb=short -m integration

test-performance: setup-integration
	@echo "⚡ Lancement des tests de performance..."
	@pytest tests/integration/ -v --tb=short -m performance

test-full: setup-integration
	@echo "🔍 Tests complets avec couverture..."
	@pytest tests/ -v --cov=src --cov-report=html --cov-report=term