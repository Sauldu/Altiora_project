# tests/test_orchestrator.py
"""
Tests pour le Orchestrator, couvrant divers scénarios, y compris les cas d'erreur.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from policies.business_rules import BusinessRules
from src.models.sfd_models import SFDAnalysisRequest
from src.orchestrator import Orchestrator


@pytest.fixture
async def orchestrator():
    """Fixture pour initialiser et fermer proprement l'orchestrateur."""
    # Initialisation des dépendances nécessaires
    starcoder = None  # Remplacez par une instance appropriée si nécessaire
    redis_client = None  # Remplacez par une instance appropriée si nécessaire
    config = None  # Remplacez par une instance appropriée si nécessaire
    model_registry = None  # Remplacez par une instance appropriée si nécessaire

    orch = Orchestrator(starcoder, redis_client, config, model_registry)
    await orch.initialize()
    yield orch
    await orch.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_success(orchestrator: Orchestrator, tmp_path: Path):
    """Test complet du pipeline avec un SFD valide."""
    sfd_path = tmp_path / "valid_sfd.txt"
    sfd_path.write_text("Spécification: Test de connexion avec email et mot de passe.")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "completed"
    assert result["metrics"]["scenarios_found"] > 0
    assert len(result["generated_tests"]) > 0
    assert "test_connexion" in result["generated_tests"][0]["test_name"]


@pytest.mark.asyncio
async def test_empty_sfd_file(orchestrator: Orchestrator, tmp_path: Path):
    """Vérifie que l'orchestrateur gère un fichier SFD vide sans erreur."""
    sfd_path = tmp_path / "empty_sfd.txt"
    sfd_path.write_text("")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error"
    assert "Le fichier de spécifications est vide" in result["error_message"]


@pytest.mark.asyncio
async def test_sfd_file_not_found(orchestrator: Orchestrator):
    """Vérifie la gestion d'un chemin de fichier SFD inexistant."""
    sfd_request = SFDAnalysisRequest(content="")

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error"
    assert "Le fichier de spécifications n'a pas été trouvé" in result["error_message"]


@pytest.mark.asyncio
@patch("src.qwen3_interface.Qwen3Interface.analyze_sfd", new_callable=AsyncMock)
async def test_qwen3_service_unavailable(mock_analyze_sfd, orchestrator: Orchestrator, tmp_path: Path):
    """Simule une panne du service Qwen3 et vérifie la gestion de l'erreur."""
    mock_analyze_sfd.side_effect = Exception("Service Qwen3 non disponible")
    sfd_path = tmp_path / "sfd.txt"
    sfd_path.write_text("Une spécification simple.")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error"
    assert "Erreur lors de l'analyse par Qwen3" in result["error_message"]


@pytest.mark.asyncio
@patch.object(BusinessRules, "validate", new_callable=AsyncMock)
async def test_business_rules_violation(mock_validate_rules, orchestrator: Orchestrator, tmp_path: Path):
    """
    Vérifie que le pipeline s'arrête si les règles métier ne sont pas respectées.
    """
    # Simuler une violation des règles métier
    mock_validate_rules.return_value = {
        "ok": False,
        "violations": ["Utilisation de time.sleep() détectée."],
    }

    sfd_path = tmp_path / "sfd_with_violation.txt"
    sfd_path.write_text("Spécification qui générera un test non conforme.")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error"
    assert "Validation des règles métier échouée" in result["error_message"]
    assert "Utilisation de time.sleep() détectée." in result["details"]


@pytest.mark.asyncio
async def test_syntax_error_in_sfd(orchestrator: Orchestrator, tmp_path: Path):
    """Vérifie la gestion d'une erreur de syntaxe dans le fichier SFD."""
    sfd_path = tmp_path / "invalid_sfd.txt"
    sfd_path.write_text("Spécification: Test de connexion avec email et mot de passe.\nSyntaxError")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error"
    assert "Erreur de syntaxe dans le fichier SFD" in result["error_message"]


@pytest.mark.asyncio
@patch("src.qwen3_interface.Qwen3Interface.analyze_sfd", new_callable=AsyncMock)
async def test_qwen3_service_timeout(mock_analyze_sfd, orchestrator: Orchestrator, tmp_path: Path):
    """Simule un délai d'attente du service Qwen3 et vérifie la gestion de l'erreur."""
    mock_analyze_sfd.side_effect = asyncio.TimeoutError("Service Qwen3 en délai d'attente")
    sfd_path = tmp_path / "sfd.txt"
    sfd_path.write_text("Une spécification simple.")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error"
    assert "Délai d'attente du service Qwen3" in result["error_message"]


@pytest.mark.asyncio
@patch("src.qwen3_interface.Qwen3Interface.analyze_sfd", new_callable=AsyncMock)
async def test_qwen3_service_invalid_response(mock_analyze_sfd, orchestrator: Orchestrator, tmp_path: Path):
    """Simule une réponse invalide du service Qwen3 et vérifie la gestion de l'erreur."""
    mock_analyze_sfd.return_value = {"error": "Réponse invalide"}
    sfd_path = tmp_path / "sfd.txt"
    sfd_path.write_text("Une spécification simple.")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error"
    assert "Réponse invalide du service Qwen3" in result["error_message"]
