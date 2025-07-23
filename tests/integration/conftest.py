# tests/integration/conftest.py
"""
Configuration des tests d'intégration
"""

import pytest
import asyncio
import redis.asyncio as redis
from pathlib import Path


@pytest.fixture(scope="session")
def integration_config():
    """Configuration pour les tests d'intégration."""
    return {
        "ollama_host": "http://localhost:11434",
        "services": {
            "ocr": "http://localhost:8001",
            "alm": "http://localhost:8002",
            "excel": "http://localhost:8003",
            "playwright": "http://localhost:8004"
        },
        "redis_url": "redis://localhost:6379"
    }


@pytest.fixture(scope="session")
async def redis_client():
    """Client Redis pour les tests."""
    client = await redis.from_url("redis://localhost:6379", decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture(scope="function")
async def clear_redis(redis_client):
    """Nettoie Redis avant chaque test."""
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


@pytest.fixture(scope="session")
async def wait_for_services():
    """Attend que tous les services soient prêts."""
    import aiohttp
    import time

    services = [
        "http://localhost:11434/health",
        "http://localhost:8001/health",
        "http://localhost:8002/health",
        "http://localhost:8003/health",
        "http://localhost:8004/health"
    ]

    async def check_service(url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    return resp.status == 200
        except:
            return False

    max_wait = 60
    start_time = time.time()

    while time.time() - start_time < max_wait:
        ready = all([await check_service(url) for url in services])
        if ready:
            break
        await asyncio.sleep(1)

    if not ready:
        pytest.skip("Services non disponibles")


# Markers personnalisés
pytest.mark.integration = pytest.mark.integration
pytest.mark.performance = pytest.mark.performance