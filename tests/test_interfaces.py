
"""
Tests unitaires pour les interfaces avec les modèles Ollama (Qwen3 et StarCoder2).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from models.starcoder2.starcoder2_interface import StarCoder2OllamaInterface, PlaywrightTestConfig, TestType as TestType


@pytest.fixture
def qwen3_interface():
    """Fixture pour l'interface Qwen3."""
    return Qwen3OllamaInterface(model_name="test-qwen3", cache_enabled=False)


@pytest.fixture
def starcoder2_interface():
    """Fixture pour l'interface StarCoder2."""
    return StarCoder2OllamaInterface(model_name="test-starcoder2", cache_enabled=False)


# --- Tests pour Qwen3Interface ---

def test_qwen3_build_prompt(qwen3_interface: Qwen3OllamaInterface):
    """Vérifie que le prompt pour l'analyse SFD est correctement formaté."""
    sfd_content = "Le système doit permettre à l'utilisateur de se connecter."
    prompt = qwen3_interface._build_prompt(sfd_content, "complete")
    assert "<|im_start|>system" in prompt
    assert "Analyse la spécification fonctionnelle suivante" in prompt
    assert sfd_content in prompt
    assert "<|im_end|>" in prompt


@pytest.mark.asyncio
async def test_qwen3_analyze_sfd_parsing(qwen3_interface: Qwen3OllamaInterface):
    """Vérifie que la réponse JSON de Qwen3 est correctement parsée."""
    mock_response = {
        "model": "test-qwen3",
        "created_at": "2023-11-23T14:02:14.43495Z",
        "response": '''```json
{
  "titre": "Analyse de la SFD",
  "scenarios": [
    {"id": "SC-01", "description": "Connexion réussie"}
  ]
}
```''',        "done": True
    }
    qwen3_interface.client = MagicMock()
    qwen3_interface.client.generate = AsyncMock(return_value=mock_response)

    result = await qwen3_interface.analyze_sfd("contenu de test")

    assert "scenarios" in result
    assert len(result["scenarios"]) == 1
    assert result["scenarios"][0]["id"] == "SC-01"


# --- Tests pour StarCoder2Interface ---

def test_starcoder2_build_prompt(starcoder2_interface: StarCoder2OllamaInterface):
    """Vérifie que le prompt pour la génération de test est correctement formaté."""
    scenario = {"description": "Tester le bouton de connexion"}
    config = PlaywrightTestConfig()
    prompt = starcoder2_interface._build_prompt(scenario, config, TestType.E2E)
    assert "<|im_start|>system" in prompt
    assert "Génère un test Playwright en Python" in prompt
    assert scenario["description"] in prompt
    assert "<|file_separator|><|im_end|>" in prompt


def test_starcoder2_extract_code(starcoder2_interface: StarCoder2OllamaInterface):
    """Teste l'extraction du code depuis la réponse du modèle."""
    raw_response = '''<|reponse|>
```python
def test_example():
    pass
```
'''
    code = starcoder2_interface._extract_code_from_response(raw_response)
    expected_code = "def test_example():\n    pass"
    assert code == expected_code


@pytest.mark.asyncio
async def test_starcoder2_generate_test_parsing(starcoder2_interface: StarCoder2OllamaInterface):
    """Vérifie que la génération de test gère correctement la réponse du modèle."""
    mock_response = {
        "response": '''<|reponse|>
```python
def test_my_scenario():
    # Ceci est un test
    assert True
```
'''
    }
    starcoder2_interface.client = MagicMock()
    starcoder2_interface.client.generate = AsyncMock(return_value=mock_response)

    scenario = {"id": "SC-01", "description": "Mon scénario"}
    config = PlaywrightTestConfig()
    result = await starcoder2_interface.generate_playwright_test(scenario, config, TestType.E2E)

    assert "code" in result
    assert "def test_my_scenario():" in result["code"]
    assert result["metadata"]["scenario_id"] == "SC-01"

