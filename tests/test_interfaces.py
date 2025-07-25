"""Tests unitaires pour les interfaces avec les modèles Ollama (Qwen3 et StarCoder2).

Ce module contient des tests pour vérifier le bon fonctionnement des
interfaces `Qwen3OllamaInterface` et `StarCoder2OllamaInterface`.
Il s'assure que les prompts sont correctement formatés, que les réponses
des modèles sont correctement parsées et que les fonctionnalités clés
de chaque interface sont opérationnelle.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from src.models.starcoder2.starcoder2_interface import StarCoder2OllamaInterface, PlaywrightTestConfig, TestType
from src.models.sfd_models import SFDAnalysisRequest # Import nécessaire pour Qwen3OllamaInterface


@pytest.fixture
def qwen3_interface():
    """Fixture pour une instance mockée de `Qwen3OllamaInterface`."

    Configure l'interface pour ne pas utiliser le cache et simule les réponses d'Ollama.
    """
    # Mocke la session aiohttp et le circuit breaker.
    mock_session = AsyncMock()
    mock_session.post.return_value.__aenter__.return_value.json.return_value = {}
    mock_session.post.return_value.__aenter__.return_value.raise_for_status.return_value = None

    mock_circuit_breaker = AsyncMock()
    mock_circuit_breaker.call.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)

    interface = Qwen3OllamaInterface(model_name="test-qwen3", cache_enabled=False)
    interface.session = mock_session
    interface.circuit_breaker = mock_circuit_breaker
    return interface


@pytest.fixture
def starcoder2_interface():
    """Fixture pour une instance mockée de `StarCoder2OllamaInterface`."

    Configure l'interface pour simuler les réponses d'Ollama.
    """
    # Mocke la session aiohttp et le circuit breaker.
    mock_session = AsyncMock()
    mock_session.post.return_value.__aenter__.return_value.json.return_value = {}
    mock_session.post.return_value.__aenter__.return_value.raise_for_status.return_value = None

    mock_circuit_breaker = AsyncMock()
    mock_circuit_breaker.call.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)

    # Mocke le ModelConfig et ModelMemoryManager pour l'initialisation.
    mock_model_config = MagicMock()
    mock_model_config.name = "test-starcoder2"
    mock_model_config.temperature = 0.7
    mock_model_config.top_p = 0.9
    mock_model_config.top_k = 40
    mock_model_config.repeat_penalty = 1.1
    mock_model_config.max_tokens = 512
    mock_model_config.num_ctx = 4096
    mock_model_config.seed = None
    mock_model_config.stop = []
    mock_model_config.api_mode = "generate"

    mock_model_memory_manager = MagicMock()
    mock_model_memory_manager.get_model.return_value = MagicMock() # Simule un modèle chargé.
    mock_model_memory_manager.loaded_models = {
        "test-starcoder2": {'tokenizer': MagicMock(decode=lambda x, **kwargs: "mocked code"), 'model': MagicMock()}
    }

    interface = StarCoder2OllamaInterface(
        config=mock_model_config,
        model_memory_manager=mock_model_memory_manager
    )
    interface.session = mock_session
    interface.circuit_breaker = mock_circuit_breaker
    return interface


# --- Tests pour Qwen3OllamaInterface ---

def test_qwen3_build_prompt(qwen3_interface: Qwen3OllamaInterface):
    """Vérifie que le prompt pour l'analyse SFD est correctement formaté."""
    sfd_request = SFDAnalysisRequest(content="Le système doit permettre à l'utilisateur de se connecter.", extraction_type="complete")
    prompt = qwen3_interface._build_prompt(sfd_request)
    assert "<|im_start|>system" in prompt
    assert "Extrayez tous les scénarios de test détaillés" in prompt
    assert sfd_request.content in prompt
    assert "<|im_end|>" in prompt


@pytest.mark.asyncio
async def test_qwen3_analyze_sfd_parsing(qwen3_interface: Qwen3OllamaInterface):
    """Vérifie que la réponse JSON de Qwen3 est correctement parsée."""
    mock_response_data = {
        "model": "test-qwen3",
        "created_at": "2023-11-23T14:02:14.43495Z",
        "response": '''{
  "scenarios": [
    {"id": "SC-01", "titre": "Connexion réussie", "objectif": "Vérifier la connexion"}
  ]
}''',
        "done": True
    }
    qwen3_interface.session.post.return_value.__aenter__.return_value.json.return_value = mock_response_data

    sfd_request = SFDAnalysisRequest(content="contenu de test", extraction_type="complete")
    result = await qwen3_interface.analyze_sfd(sfd_request)

    assert "scenarios" in result
    assert len(result["scenarios"]) == 1
    assert result["scenarios"][0]["id"] == "SC-01"
    assert result["scenarios"][0]["titre"] == "Connexion réussie"


# --- Tests pour StarCoder2OllamaInterface ---

def test_starcoder2_build_prompt(starcoder2_interface: StarCoder2OllamaInterface):
    """Vérifie que le prompt pour la génération de test est correctement formaté."""
    scenario = {"titre": "Tester le bouton de connexion", "objectif": "Vérifier le clic", "etapes": ["Cliquer sur le bouton."]}
    config = PlaywrightTestConfig()
    prompt = starcoder2_interface._build_prompt(scenario, config, TestType.E2E)
    assert "Generate a complete Playwright test in Python." in prompt
    assert scenario["titre"] in prompt
    assert "Browser: chromium" in prompt
    assert "```python" in prompt


def test_starcoder2_extract_code(starcoder2_interface: StarCoder2OllamaInterface):
    """Teste l'extraction du code depuis la réponse brute du modèle."""
    raw_response = '''<|reponse|>
```python
def test_example():
    page.goto("http://example.com")
    expect(page).to_have_title("Example")
```
'''
    code = starcoder2_interface._extract_code(raw_response)
    expected_code = "def test_example():\n    page.goto(\"http://example.com\")\n    expect(page).to_have_title(\"Example\")"
    assert code == expected_code


@pytest.mark.asyncio
async def test_starcoder2_generate_test_parsing(starcoder2_interface: StarCoder2OllamaInterface):
    """Vérifie que la génération de test gère correctement la réponse du modèle et les métadonnées."""
    mock_response_data = {
        "response": '''<|reponse|>
```python
def test_my_scenario():
    # Ceci est un test Playwright généré.
    await page.goto("https://test.com")
    expect(page).to_have_title("Test Page")
```
'''
    }
    starcoder2_interface.session.post.return_value.__aenter__.return_value.json.return_value = mock_response_data

    scenario = {"id": "SC-01", "titre": "Mon scénario de test", "objectif": "Vérifier quelque chose"}
    config = PlaywrightTestConfig()
    result = await starcoder2_interface.generate_playwright_test(scenario, config, TestType.E2E)

    assert "code" in result
    assert "def test_my_scenario():" in result["code"]
    assert result["test_type"] == TestType.E2E.value
    assert result["uses_page_object"] == config.use_page_object
    assert "metadata" in result
    assert result["metadata"]["scenario_title"] == "Mon scénario de test"