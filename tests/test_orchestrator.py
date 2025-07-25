# tests/test_orchestrator.py
"""Tests d'intégration pour la classe Orchestrator.

Ce module contient des tests qui vérifient le comportement de l'orchestrateur
dans divers scénarios, y compris les cas de succès du pipeline complet,
la gestion des fichiers SFD vides ou manquants, et la gestion des erreurs
provenant des services dépendants (Qwen3, règles métier).
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
    """Fixture pour initialiser et fermer proprement l'orchestrateur pour chaque test."

    Cette fixture crée une instance de l'Orchestrator et s'assure que ses
    dépendances (stubs ou mocks) sont correctement configurées pour les tests.
    """
    # Mocke les dépendances de l'orchestrateur pour l'isoler.
    starcoder_mock = AsyncMock()
    redis_client_mock = AsyncMock()
    config_mock = MagicMock()
    model_registry_mock = MagicMock()

    # Crée l'instance de l'Orchestrator avec les mocks.
    orch = Orchestrator(starcoder_mock, redis_client_mock, config_mock, model_registry_mock)
    # Initialise l'orchestrateur (charge la config, etc.).
    await orch.initialize()
    yield orch
    # Ferme l'orchestrateur après le test.
    await orch.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_success(orchestrator: Orchestrator, tmp_path: Path):
    """Teste le scénario de succès du pipeline complet avec un fichier SFD valide."

    Vérifie que l'orchestrateur peut traiter une SFD de bout en bout,
    extraire des scénarios, générer des tests et retourner un statut 'completed'.
    """
    # Prépare un fichier SFD valide temporaire.
    sfd_content = "Spécification: Test de connexion avec email et mot de passe. Scénario: Connexion réussie."
    sfd_path = tmp_path / "valid_sfd.txt"
    sfd_path.write_text(sfd_content)
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    # Mocke la méthode `analyze_sfd` de Qwen3 pour simuler une réponse réussie.
    orchestrator.qwen3.analyze_sfd.return_value = {
        "scenarios": [
            {"id": "SC-001", "titre": "Connexion réussie", "description": "Test de connexion"}
        ]
    }
    # Mocke la méthode `generate_playwright_test` de Starcoder2.
    orchestrator.starcoder.generate_playwright_test.return_value = {"code": "def test_connexion(): pass", "test_name": "test_connexion"}

    # Exécute le pipeline.
    result = await orchestrator.process_sfd_to_tests(sfd_request)

    # Assertions sur le résultat.
    assert result["status"] == "completed", "Le pipeline devrait se terminer avec le statut 'completed'."
    assert result["metrics"]["scenarios_found"] > 0, "Des scénarios devraient être trouvés."
    assert len(result["generated_tests"]) > 0, "Des tests devraient être générés."
    assert "test_connexion" in result["generated_tests"][0]["test_name"], "Le nom du test généré devrait être correct."


@pytest.mark.asyncio
async def test_empty_sfd_file(orchestrator: Orchestrator, tmp_path: Path):
    """Vérifie que l'orchestrateur gère correctement un fichier SFD vide."

    Le pipeline devrait détecter le fichier vide et retourner un statut d'erreur.
    """
    sfd_path = tmp_path / "empty_sfd.txt"
    sfd_path.write_text("") # Crée un fichier vide.
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error", "Le pipeline devrait retourner un statut 'error'."
    assert "Le fichier de spécifications est vide" in result["error_message"], "Le message d'erreur devrait indiquer un fichier vide."


@pytest.mark.asyncio
async def test_sfd_file_not_found(orchestrator: Orchestrator):
    """Vérifie la gestion d'un chemin de fichier SFD inexistant."

    L'orchestrateur devrait retourner un statut d'erreur si le fichier n'est pas trouvé.
    """
    # Crée une requête avec un contenu vide, simulant un fichier non trouvé.
    sfd_request = SFDAnalysisRequest(content="")

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error", "Le pipeline devrait retourner un statut 'error'."
    assert "Le fichier de spécifications n'a pas été trouvé" in result["error_message"], "Le message d'erreur devrait indiquer un fichier non trouvé."


@pytest.mark.asyncio
@patch("src.models.qwen3.qwen3_interface.Qwen3OllamaInterface.analyze_sfd", new_callable=AsyncMock)
async def test_qwen3_service_unavailable(mock_analyze_sfd: AsyncMock, orchestrator: Orchestrator, tmp_path: Path):
    """Simule une panne du service Qwen3 et vérifie la gestion de l'erreur par l'orchestrateur."

    L'orchestrateur devrait capturer l'exception et retourner un statut d'erreur.
    """
    mock_analyze_sfd.side_effect = Exception("Service Qwen3 non disponible") # Simule une exception.
    sfd_path = tmp_path / "sfd.txt"
    sfd_path.write_text("Une spécification simple.")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error", "Le pipeline devrait retourner un statut 'error'."
    assert "Erreur lors de l'analyse par Qwen3" in result["error_message"], "Le message d'erreur devrait refléter la panne de Qwen3."


@pytest.mark.asyncio
@patch.object(BusinessRules, "validate", new_callable=AsyncMock)
async def test_business_rules_violation(mock_validate_rules: AsyncMock, orchestrator: Orchestrator, tmp_path: Path):
    """Vérifie que le pipeline s'arrête si les règles métier ne sont pas respectées."

    Simule une violation des règles métier et s'assure que l'orchestrateur
    détecte l'échec et retourne un statut d'erreur approprié.
    """
    # Simule une violation des règles métier en faisant retourner `False` par le validateur.
    mock_validate_rules.return_value = {
        "ok": False,
        "violations": ["Utilisation de time.sleep() détectée."],
    }

    sfd_path = tmp_path / "sfd_with_violation.txt"
    sfd_path.write_text("Spécification qui générera un test non conforme.")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error", "Le pipeline devrait retourner un statut 'error'."
    assert "Validation des règles métier échouée" in result["error_message"], "Le message d'erreur devrait indiquer une violation des règles métier."
    assert "Utilisation de time.sleep() détectée." in result["details"], "Les détails de la violation devraient être présents."


@pytest.mark.asyncio
async def test_syntax_error_in_sfd(orchestrator: Orchestrator, tmp_path: Path):
    """Vérifie la gestion d'une erreur de syntaxe dans le fichier SFD."

    Simule un fichier SFD avec une erreur de syntaxe et s'assure que l'orchestrateur
    la détecte et retourne un statut d'erreur.
    """
    sfd_path = tmp_path / "invalid_sfd.txt"
    sfd_path.write_text("Spécification: Test de connexion avec email et mot de passe.\nSyntaxError: invalid syntax")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error", "Le pipeline devrait retourner un statut 'error'."
    assert "Erreur de syntaxe dans le fichier SFD" in result["error_message"], "Le message d'erreur devrait indiquer une erreur de syntaxe."


@pytest.mark.asyncio
@patch("src.models.qwen3.qwen3_interface.Qwen3OllamaInterface.analyze_sfd", new_callable=AsyncMock)
async def test_qwen3_service_timeout(mock_analyze_sfd: AsyncMock, orchestrator: Orchestrator, tmp_path: Path):
    """Simule un délai d'attente (timeout) du service Qwen3 et vérifie la gestion de l'erreur."

    L'orchestrateur devrait capturer le `asyncio.TimeoutError` et retourner un statut d'erreur.
    """
    mock_analyze_sfd.side_effect = asyncio.TimeoutError("Service Qwen3 en délai d'attente")
    sfd_path = tmp_path / "sfd.txt"
    sfd_path.write_text("Une spécification simple.")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error", "Le pipeline devrait retourner un statut 'error'."
    assert "Délai d'attente du service Qwen3" in result["error_message"], "Le message d'erreur devrait indiquer un timeout."


@pytest.mark.asyncio
@patch("src.models.qwen3.qwen3_interface.Qwen3OllamaInterface.analyze_sfd", new_callable=AsyncMock)
async def test_qwen3_service_invalid_response(mock_analyze_sfd: AsyncMock, orchestrator: Orchestrator, tmp_path: Path):
    """Simule une réponse invalide du service Qwen3 et vérifie la gestion de l'erreur."

    L'orchestrateur devrait détecter la réponse invalide et retourner un statut d'erreur.
    """
    # Simule une réponse de Qwen3 qui ne contient pas les données attendues.
    mock_analyze_sfd.return_value = {"error": "Réponse invalide"}
    sfd_path = tmp_path / "sfd.txt"
    sfd_path.write_text("Une spécification simple.")
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

    result = await orchestrator.process_sfd_to_tests(sfd_request)

    assert result["status"] == "error", "Le pipeline devrait retourner un statut 'error'."
    assert "Réponse invalide du service Qwen3" in result["error_message"], "Le message d'erreur devrait indiquer une réponse invalide."