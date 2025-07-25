# tests/test_retry_handler.py
"""Tests unitaires pour le gestionnaire de retry (`RetryHandler`).

Ce module contient des tests pour vérifier le bon fonctionnement du décorateur
`@RetryHandler.with_retry`, y compris les scénarios de succès après échec
et d'épuisement des tentatives.
"""

import pytest
import asyncio
import logging

from src.utils.retry_handler import RetryHandler

logger = logging.getLogger(__name__)


@pytest.fixture
def retry_handler_instance():
    """Fixture pour fournir une instance de `RetryHandler` pour les tests."

    Utilise les valeurs par défaut pour les paramètres du gestionnaire.
    """
    return RetryHandler()


@pytest.mark.asyncio
async def test_retry_success(retry_handler_instance: RetryHandler):
    """Teste que la fonction décorée réussit après un ou plusieurs échecs initiaux."

    Vérifie que la fonction est retentée le nombre de fois nécessaire avant de réussir.
    """
    call_count = 0

    @retry_handler_instance.with_retry(max_attempts=3, exceptions=(ValueError,))
    async def flaky_function():
        nonlocal call_count
        call_count += 1
        logger.info(f"Appel de flaky_function, tentative #{call_count}")
        if call_count < 2:
            raise ValueError("Échec simulé")
        return "succès"

    result = await flaky_function()
    assert result == "succès", "La fonction devrait réussir après retry."
    assert call_count == 2, "La fonction devrait être appelée 2 fois (1 échec + 1 succès)."


@pytest.mark.asyncio
async def test_retry_exhaustion(retry_handler_instance: RetryHandler):
    """Teste que le retry s'arrête après avoir épuisé le nombre maximal de tentatives."

    Vérifie qu'une exception est levée après le nombre maximal de tentatives.
    """
    call_count = 0

    @retry_handler_instance.with_retry(max_attempts=2, exceptions=(ValueError,))
    async def always_failing_function():
        nonlocal call_count
        call_count += 1
        logger.info(f"Appel de always_failing_function, tentative #{call_count}")
        raise ValueError("Échec permanent")

    with pytest.raises(ValueError) as excinfo:
        await always_failing_function()
    
    assert "Échec permanent" in str(excinfo.value), "L'exception levée devrait être celle de la fonction."
    assert call_count == 2, "La fonction devrait être appelée exactement 2 fois."


@pytest.mark.asyncio
async def test_retry_different_exception_type(retry_handler_instance: RetryHandler):
    """Teste que le retry ne se déclenche que pour les types d'exceptions spécifiés."

    Vérifie qu'une exception non spécifiée n'est pas retentée.
    """
    call_count = 0

    @retry_handler_instance.with_retry(max_attempts=3, exceptions=(ValueError,))
    async def specific_exception_function():
        nonlocal call_count
        call_count += 1
        logger.info(f"Appel de specific_exception_function, tentative #{call_count}")
        if call_count == 1:
            raise TypeError("Type d'erreur inattendu") # Cette exception ne devrait pas être retentée.
        return "succès"

    with pytest.raises(TypeError) as excinfo:
        await specific_exception_function()
    
    assert "Type d'erreur inattendu" in str(excinfo.value), "L'exception TypeError devrait être levée immédiatement."
    assert call_count == 1, "La fonction ne devrait être appelée qu'une seule fois."


@pytest.mark.asyncio
async def test_circuit_breaker_open(retry_handler_instance: RetryHandler):
    """Teste que le disjoncteur s'ouvre après un certain nombre d'échecs."

    Vérifie que les appels ultérieurs sont bloqués tant que le disjoncteur est ouvert.
    """
    service_name = "test_service"
    call_count = 0

    @retry_handler_instance.circuit_breaker
    async def unreliable_service():
        nonlocal call_count
        call_count += 1
        raise Exception("Service en panne")

    # Provoque l'ouverture du disjoncteur.
    for _ in range(retry_handler_instance.failure_threshold):
        with pytest.raises(Exception):
            await unreliable_service()
    
    assert retry_handler_instance._is_open.get(service_name), "Le disjoncteur devrait être ouvert."

    # Tente un appel alors que le disjoncteur est ouvert.
    with pytest.raises(Exception) as excinfo:
        await unreliable_service()
    assert "Circuit breaker is open" in str(excinfo.value), "L'appel devrait être bloqué par le disjoncteur."
    assert call_count == retry_handler_instance.failure_threshold, "Aucun appel supplémentaire ne devrait avoir eu lieu."


@pytest.mark.asyncio
async def test_circuit_breaker_reset(retry_handler_instance: RetryHandler):
    """Teste que le disjoncteur se réinitialise après le timeout de récupération."

    Vérifie que le disjoncteur passe de l'état ouvert à fermé après le délai.
    """
    service_name = "test_service_reset"
    call_count = 0

    @retry_handler_instance.circuit_breaker
    async def intermittently_failing_service():
        nonlocal call_count
        call_count += 1
        if call_count <= retry_handler_instance.failure_threshold:
            raise Exception("Échec initial")
        return "Service récupéré"

    # Provoque l'ouverture du disjoncteur.
    for _ in range(retry_handler_instance.failure_threshold):
        with pytest.raises(Exception):
            await intermittently_failing_service()
    
    assert retry_handler_instance._is_open.get(service_name), "Le disjoncteur devrait être ouvert."

    # Attend le timeout de récupération.
    await asyncio.sleep(retry_handler_instance.recovery_timeout + 0.1)

    # Le premier appel après le timeout devrait tenter de se refermer.
    result = await intermittently_failing_service()
    assert result == "Service récupéré", "Le service devrait se récupérer."
    assert not retry_handler_instance._is_open.get(service_name), "Le disjoncteur devrait être fermé."