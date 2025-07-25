# tests/conftest.py
"""Fichier de configuration pour Pytest.

Ce fichier contient des fixtures (fonctions de configuration) qui sont
automatiquement découvertes par Pytest et peuvent être utilisées dans
les tests. Elles sont souvent utilisées pour configurer des environnements
de test, mocker des dépendances ou fournir des données de test.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_redis():
    """Fixture mockant un client Redis asynchrone."

    Simule les méthodes `get` et `set` pour les tests qui interagissent avec Redis.
    """
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    return redis

@pytest.fixture
def mock_ollama():
    """Fixture mockant un client Ollama."

    Simule la méthode `generate` pour les tests qui interagissent avec Ollama.
    """
    ollama = MagicMock()
    ollama.generate.return_value = {"response": "mocked response"}
    return ollama

@pytest.fixture
def mock_database():
    """Fixture mockant un client de base de données."

    Simule les opérations CRUD (`query`, `insert`, `update`, `delete`).
    """
    db = MagicMock()
    db.query.return_value = []
    db.insert.return_value = True
    db.update.return_value = True
    db.delete.return_value = True
    return db

@pytest.fixture
def mock_http_client():
    """Fixture mockant un client HTTP asynchrone (ex: `httpx`)."

    Simule les requêtes `get` et `post`.
    """
    http_client = AsyncMock()
    http_client.get.return_value.__aenter__.return_value.json.return_value = {}
    http_client.post.return_value.__aenter__.return_value.json.return_value = {}
    return http_client

@pytest.fixture
def mock_filesystem():
    """Fixture mockant les opérations du système de fichiers."

    Simule les lectures et écritures de fichiers.
    """
    fs = MagicMock()
    fs.open.return_value.__enter__.return_value.read.return_value = "mocked file content"
    fs.open.return_value.__aenter__.return_value.write.return_value = None
    return fs

@pytest.fixture
def mock_logger():
    """Fixture mockant un logger."

    Simule les méthodes de logging (`info`, `error`, `warning`).
    """
    logger = MagicMock()
    logger.info.return_value = None
    logger.error.return_value = None
    logger.warning.return_value = None
    return logger

@pytest.fixture
def mock_config():
    """Fixture mockant un objet de configuration."

    Simule la méthode `get` pour récupérer des valeurs de configuration.
    """
    config = MagicMock()
    config.get.return_value = "mocked config value"
    return config

@pytest.fixture
def mock_service():
    """Fixture mockant un client de service générique."

    Simule la méthode `call`.
    """
    service = MagicMock()
    service.call.return_value = "mocked service response"
    return service
