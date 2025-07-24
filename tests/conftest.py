# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    return redis

@pytest.fixture
def mock_ollama():
    """Mock Ollama client"""
    ollama = MagicMock()
    ollama.generate.return_value = {"response": "mocked response"}
    return ollama

@pytest.fixture
def mock_database():
    """Mock database client"""
    db = MagicMock()
    db.query.return_value = []
    db.insert.return_value = True
    db.update.return_value = True
    db.delete.return_value = True
    return db

@pytest.fixture
def mock_http_client():
    """Mock HTTP client"""
    http_client = AsyncMock()
    http_client.get.return_value.__aenter__.return_value.json.return_value = {}
    http_client.post.return_value.__aenter__.return_value.json.return_value = {}
    return http_client

@pytest.fixture
def mock_filesystem():
    """Mock filesystem operations"""
    fs = MagicMock()
    fs.open.return_value.__enter__.return_value.read.return_value = "mocked file content"
    fs.open.return_value.__aenter__.return_value.write.return_value = None
    return fs

@pytest.fixture
def mock_logger():
    """Mock logger"""
    logger = MagicMock()
    logger.info.return_value = None
    logger.error.return_value = None
    logger.warning.return_value = None
    return logger

@pytest.fixture
def mock_config():
    """Mock configuration"""
    config = MagicMock()
    config.get.return_value = "mocked config value"
    return config

@pytest.fixture
def mock_service():
    """Mock service client"""
    service = MagicMock()
    service.call.return_value = "mocked service response"
    return service