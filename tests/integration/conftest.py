# tests/integration/conftest.py
"""Configuration des tests d'intégration pour le projet Altiora.

Ce fichier contient des fixtures Pytest spécifiques aux tests d'intégration.
Elles sont utilisées pour configurer l'environnement de test, notamment
la connexion à Redis et l'attente de la disponibilité des microservices.
"""

import pytest
import asyncio
import redis.asyncio as redis
from pathlib import Path
from typing import Dict, Any
import httpx # Utilisé pour les vérifications de service.
import logging

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def integration_config() -> Dict[str, Any]:
    """Fixture fournissant la configuration de base pour les tests d'intégration."

    Returns:
        Un dictionnaire contenant les URLs des services et de Redis.
    """
    return {
        "ollama_host": "http://localhost:11434",
        "services": {
            "ocr": "http://localhost:8001",
            "alm": "http://localhost:8002",
            "excel": "http://localhost:8003",
            "playwright": "http://localhost:8004",
            "dash": "http://localhost:8050", # Ajouté pour le service Dash.
        },
        "redis_url": "redis://localhost:6379"
    }


@pytest.fixture(scope="session")
async def redis_client(integration_config: Dict[str, Any]) -> redis.Redis:
    """Fixture fournissant un client Redis asynchrone pour les tests."

    Le client est connecté à l'URL spécifiée dans la configuration d'intégration.
    """
    client = await redis.from_url(integration_config["redis_url"], decode_responses=True)
    logger.info("Connexion au client Redis pour les tests d'intégration.")
    yield client
    logger.info("Fermeture de la connexion Redis pour les tests d'intégration.")
    await client.aclose()


@pytest.fixture(scope="function")
async def clear_redis(redis_client: redis.Redis):
    """Fixture nettoyant la base de données Redis avant et après chaque test."

    Assure un état propre pour chaque test d'intégration.
    """
    logger.info("Nettoyage de Redis avant le test.")
    await redis_client.flushdb()
    yield
    logger.info("Nettoyage de Redis après le test.")
    await redis_client.flushdb()


@pytest.fixture(scope="session", autouse=True) # autouse=True signifie que cette fixture est exécutée automatiquement.
async def wait_for_services(integration_config: Dict[str, Any]):
    """Fixture attendant que tous les microservices nécessaires soient prêts et accessibles."

    Cette fixture est cruciale pour les tests d'intégration, car elle garantit
    que toutes les dépendances externes sont opérationnelles avant l'exécution des tests.
    """
    service_urls = [
        integration_config["ollama_host"] + "/api/tags", # Endpoint pour vérifier Ollama.
        integration_config["services"]["ocr"] + "/health",
        integration_config["services"]["alm"] + "/health",
        integration_config["services"]["excel"] + "/health",
        integration_config["services"]["playwright"] + "/health",
        integration_config["services"]["dash"] + "/health",
    ]

    async def check_service(url: str) -> bool:
        """Vérifie la disponibilité d'un service en envoyant une requête HTTP GET à son URL."

        Args:
            url: L'URL du service à vérifier.

        Returns:
            True si le service répond avec un statut 200, False sinon.
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except httpx.RequestError as e:
            logger.debug(f"Service {url} non joignable : {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la vérification du service {url}: {e}")
            return False

    max_wait_time = 120 # Temps maximal d'attente en secondes.
    check_interval = 1 # Intervalle entre les vérifications en secondes.
    start_time = asyncio.get_event_loop().time()

    logger.info(f"Attente de la disponibilité des services ({max_wait_time}s max)...")
    while asyncio.get_event_loop().time() - start_time < max_wait_time:
        # Exécute toutes les vérifications de service en parallèle.
        ready_checks = await asyncio.gather(*[check_service(url) for url in service_urls])
        if all(ready_checks):
            logger.info("✅ Tous les services sont prêts.")
            return
        logger.info("Services non encore prêts, nouvelle tentative dans 1 seconde...")
        await asyncio.sleep(check_interval)

    pytest.fail(f"Les services n'ont pas démarré après {max_wait_time} secondes. Les tests d'intégration ne peuvent pas être exécutés.")


# Marqueurs personnalisés pour Pytest.
pytest.mark.integration = pytest.mark.integration
pytest.mark.performance = pytest.mark.performance
