# Variables d'Environnement - Documentation

## Vue d'ensemble

Ce document décrit toutes les variables d'environnement utilisées dans le projet Altiora.

## Variables Générales

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `ENVIRONMENT` | Environnement d'exécution | `development`, `staging`, `production`, `test` | `development` | ✅ |
| `DEBUG` | Mode debug activé | `true`, `false` | `false` | ❌ |
| `LOG_LEVEL` | Niveau de logging | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` | ❌ |

## Configuration Ollama

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `OLLAMA_HOST` | URL du serveur Ollama | URL complète | `http://localhost:11434` | ✅ |
| `OLLAMA_TIMEOUT` | Timeout des requêtes (secondes) | Entier | `180` | ❌ |
| `OLLAMA_KEEP_ALIVE` | Durée de maintien des modèles en mémoire | Format durée (ex: `30m`) | `30m` | ❌ |
| `QWEN3_MODEL` | Nom du modèle Qwen3 | Chaîne | `qwen3-sfd-analyzer` | ✅ |
| `STARCODER2_MODEL` | Nom du modèle StarCoder2 | Chaîne | `starcoder2-playwright` | ✅ |

## Configuration Redis

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `REDIS_URL` | URL de connexion Redis | Format `redis://[password@]host:port/db` | `redis://localhost:6379` | ✅ |
| `REDIS_PASSWORD` | Mot de passe Redis | Chaîne | *(vide)* | ❌ (✅ en prod) |
| `REDIS_DB` | Numéro de base Redis | 0-15 | `0` | ❌ |
| `REDIS_TTL_SFD` | TTL cache analyses SFD (sec) | Entier | `86400` (24h) | ❌ |
| `REDIS_TTL_TESTS` | TTL cache tests générés (sec) | Entier | `43200` (12h) | ❌ |
| `REDIS_TTL_OCR` | TTL cache résultats OCR (sec) | Entier | `604800` (7j) | ❌ |
| `REDIS_TTL_MODEL` | TTL cache réponses modèles (sec) | Entier | `3600` (1h) | ❌ |

## Services Microservices

### Service d'Authentification

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `DATABASE_URL` | URL de la base de données d'authentification | Chaîne de connexion | `sqlite:///./auth.db` | ✅ |
| `JWT_SECRET_KEY` | Clé secrète JWT | Chaîne (min 32 car.) | *(généré)* | ✅ |
| `JWT_ALGORITHM` | Algorithme JWT | `HS256`, `HS384`, `HS512` | `HS256` | ❌ |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Durée de vie du token (minutes) | Entier | `60` | ❌ |

### Service OCR

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `OCR_SERVICE_HOST` | Hôte du service OCR | Nom d'hôte/IP | `localhost` | ✅ |
| `OCR_SERVICE_PORT` | Port du service OCR | 1-65535 | `8001` | ✅ |
| `OCR_SERVICE_TIMEOUT` | Timeout OCR (secondes) | Entier | `60` | ❌ |
| `DOCTOPLUS_CONFIG` | Chemin config Doctoplus | Chemin absolu | `/app/config/config.json` | ❌ |

### Service ALM

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `ALM_SERVICE_HOST` | Hôte du service ALM | Nom d'hôte/IP | `localhost` | ✅ |
| `ALM_SERVICE_PORT` | Port du service ALM | 1-65535 | `8002` | ✅ |
| `ALM_SERVICE_TIMEOUT` | Timeout ALM (secondes) | Entier | `120` | ❌ |
| `ALM_API_URL` | URL du serveur ALM réel | URL complète | `http://alm-server:8080` | ❌ |
| `ALM_API_KEY` | Clé API pour ALM | Chaîne | *(vide)* | ❌ |

### Service Excel

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `EXCEL_SERVICE_HOST` | Hôte du service Excel | Nom d'hôte/IP | `localhost` | ✅ |
| `EXCEL_SERVICE_PORT` | Port du service Excel | 1-65535 | `8003` | ✅ |
| `EXCEL_SERVICE_TIMEOUT` | Timeout Excel (secondes) | Entier | `60` | ❌ |

### Service Playwright

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `PLAYWRIGHT_SERVICE_HOST` | Hôte du service Playwright | Nom d'hôte/IP | `localhost` | ✅ |
| `PLAYWRIGHT_SERVICE_PORT` | Port du service Playwright | 1-65535 | `8004` | ✅ |
| `PLAYWRIGHT_SERVICE_TIMEOUT` | Timeout Playwright (secondes) | Entier | `300` | ❌ |
| `PLAYWRIGHT_WORKERS` | Nombre de workers parallèles | Entier | `4` | ❌ |
| `PLAYWRIGHT_BROWSER` | Navigateur par défaut | `chromium`, `firefox`, `webkit` | `chromium` | ❌ |
| `PLAYWRIGHT_HEADED` | Mode avec interface graphique | `true`, `false` | `false` | ❌ |
| `PLAYWRIGHT_SCREENSHOT_ON_FAILURE` | Screenshots sur échec | `true`, `false` | `true` | ❌ |
| `PLAYWRIGHT_VIDEO_ON_FAILURE` | Vidéos sur échec | `true`, `false` | `true` | ❌ |

## Sécurité

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `RATE_LIMIT_ENABLED` | Limitation de débit activée | `true`, `false` | `true` | ❌ |
| `RATE_LIMIT_REQUESTS` | Nombre max de requêtes | Entier | `100` | ❌ |
| `RATE_LIMIT_WINDOW_SECONDS` | Fenêtre de temps (secondes) | Entier | `60` | ❌ |
| `ALLOWED_ORIGINS` | Origines CORS autorisées | Liste séparée par virgules | `*` | ❌ |

## Chemins et Répertoires

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `DATA_DIR` | Répertoire des données | Chemin | `./data` | ❌ |
| `MODELS_DIR` | Répertoire des modèles | Chemin | `./models` | ❌ |
| `LOGS_DIR` | Répertoire des logs | Chemin | `./logs` | ❌ |
| `REPORTS_DIR` | Répertoire des rapports | Chemin | `./reports` | ❌ |
| `TEMP_DIR` | Répertoire temporaire | Chemin | `./temp` | ❌ |
| `CACHE_DIR` | Répertoire de cache | Chemin | `./cache` | ❌ |

## Pipeline d'Orchestration

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `PIPELINE_MAX_PARALLEL_TESTS` | Tests max en parallèle | Entier | `5` | ❌ |
| `PIPELINE_MAX_PARALLEL_SCENARIOS` | Scénarios max en parallèle | Entier | `10` | ❌ |
| `PIPELINE_FALLBACK_ENABLED` | Mode fallback activé | `true`, `false` | `true` | ❌ |
| `PIPELINE_RETRY_MAX_ATTEMPTS` | Tentatives max de retry | Entier | `3` | ❌ |
| `PIPELINE_RETRY_BACKOFF_FACTOR` | Facteur de backoff | Décimal | `2.0` | ❌ |

## Docker (si utilisation avec Docker Compose)

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `COMPOSE_PROJECT_NAME` | Nom du projet Docker | Chaîne | `altiora` | ❌ |
| `DOCKER_BUILDKIT` | Utiliser BuildKit | `0`, `1` | `1` | ❌ |
| `OLLAMA_MEMORY_LIMIT` | Limite mémoire Ollama | Format Docker | `12G` | ❌ |
| `OLLAMA_CPU_LIMIT` | Limite CPU Ollama | Nombre | `8` | ❌ |

## Développement

| Variable | Description | Valeurs | Défaut | Requis |
|----------|-------------|---------|---------|--------|
| `MOCK_OCR_SERVICE` | Simuler le service OCR | `true`, `false` | `false` | ❌ |
| `MOCK_ALM_SERVICE` | Simuler le service ALM | `true`, `false` | `false` | ❌ |
| `USE_LOCAL_MODELS` | Utiliser modèles locaux | `true`, `false` | `false` | ❌ |
