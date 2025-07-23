"""
Tests pour le Orchestrator, couvrant divers scénarios, y compris les cas d'erreur.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.orchestrator import Orchestrator
from policies.business_rules import BusinessRules


@pytest.fixture
async def orchestrator():
    """Fixture pour initialiser et fermer proprement l'orchestrateur."""
    orch = Orchestrator()
    await orch.initialize()
    yield orch
    await orch.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_success(orchestrator: Orchestrator, tmp_path: Path):
    """Test complet du pipeline avec un SFD valide."""
    sfd_path = tmp_path / "valid_sfd.txt"
    sfd_path.write_text("Spécification: Test de connexion avec email et mot de passe.")

    result = await orchestrator.process_sfd_to_tests(str(sfd_path))

    assert result["status"] == "completed"
    assert result["metrics"]["scenarios_found"] > 0
    assert len(result["generated_tests"]) > 0
    assert "test_connexion" in result["generated_tests"][0]["test_name"]


@pytest.mark.asyncio
async def test_empty_sfd_file(orchestrator: Orchestrator, tmp_path: Path):
    """Vérifie que l'orchestrateur gère un fichier SFD vide sans erreur."""
    sfd_path = tmp_path / "empty_sfd.txt"
    sfd_path.write_text("")

    result = await orchestrator.process_sfd_to_tests(str(sfd_path))

    assert result["status"] == "error"
    assert "Le fichier de spécifications est vide" in result["error_message"]


@pytest.mark.asyncio
async def test_sfd_file_not_found(orchestrator: Orchestrator):
    """Vérifie la gestion d'un chemin de fichier SFD inexistant."""
    result = await orchestrator.process_sfd_to_tests("non_existent_file.txt")

    assert result["status"] == "error"
    assert "Le fichier de spécifications n'a pas été trouvé" in result["error_message"]


@pytest.mark.asyncio
@patch("src.qwen3_interface.Qwen3Interface.analyze_sfd", new_callable=AsyncMock)
async def test_qwen3_service_unavailable(mock_analyze_sfd, orchestrator: Orchestrator, tmp_path: Path):
    """Simule une panne du service Qwen3 et vérifie la gestion de l'erreur."""
    mock_analyze_sfd.side_effect = Exception("Service Qwen3 non disponible")
    sfd_path = tmp_path / "sfd.txt"
    sfd_path.write_text("Une spécification simple.")

    result = await orchestrator.process_sfd_to_tests(str(sfd_path))

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

    result = await orchestrator.process_sfd_to_tests(str(sfd_path))

    assert result["status"] == "error"
    assert "Validation des règles métier échouée" in result["error_message"]
    assert "Utilisation de time.sleep() détectée." in result["details"]
