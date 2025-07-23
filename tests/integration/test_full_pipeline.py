# tests/integration/test_full_pipeline.py
"""
Tests d'intégration pour le pipeline complet SFD → Tests Playwright
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from typing import Dict, List, Any

from src.core.altiora_assistant import AltioraQAAssistant
from src.models.sfd_models import SFDAnalysisRequest
from src.core.altiora_assistant import AltioraQAAssistant
from src.models.sfd_models import SFDAnalysisRequest
from services.ocr.ocr_wrapper import extract_with_doctoplus


@pytest.fixture(scope="session")
async def full_orchestrator():
    """Fixture pour l'orchestrateur complet."""
    orchestrator = Orchestrator()
    await orchestrator.initialize()
    yield orchestrator
    await orchestrator.close()


@pytest.fixture
def sample_sfd_content():
    """Contenu SFD de test complet."""
    return """
# Spécification Fonctionnelle - Module Authentification

## 1. Connexion Utilisateur
- **Objectif**: Permettre aux utilisateurs de se connecter de manière sécurisée
- **Acteurs**: Utilisateur authentifié, Système
- **Préconditions**: L'utilisateur a un compte actif

### 1.1 Scénario: Connexion réussie
- **Description**: L'utilisateur se connecte avec des identifiants valides
- **Étapes**:
  1. L'utilisateur accède à la page de connexion
  2. Il saisit son email valide
  3. Il saisit son mot de passe valide
  4. Il clique sur "Se connecter"
  5. Il est redirigé vers le tableau de bord
- **Résultat attendu**: Accès autorisé au tableau de bord

### 1.2 Scénario: Échec de connexion
- **Description**: L'utilisateur entre des identifiants invalides
- **Étapes**:
  1. L'utilisateur accède à la page de connexion
  2. Il saisit des identifiants incorrects
  3. Il clique sur "Se connecter"
- **Résultat attendu**: Message d'erreur "Identifiants invalides"

## 2. Récupération de mot de passe
- **Scénario**: L'utilisateur oublie son mot de passe
- **Étapes**:
  1. Cliquer sur "Mot de passe oublié"
  2. Saisir l'email
  3. Recevoir le lien de réinitialisation
  4. Réinitialiser le mot de passe
"""


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sfd_to_test_pipeline_complete(full_orchestrator, tmp_path: Path):
    """Test complet du pipeline SFD → Tests Playwright."""

    # 1. Préparation du fichier SFD
    sfd_path = tmp_path / "complete_sfd.txt"
    sfd_path.write_text(sample_sfd_content)

    # 2. Configuration du test
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text(), extraction_type=config["extraction_type"])

    # 3. Exécution du pipeline
    result = await full_orchestrator.analyze_sfd(sfd_request)

    # 4. Assertions
    assert result["status"] == "completed"

    # Vérification des métriques
    metrics = result["metrics"]
    assert metrics["scenarios_found"] >= 3  # Connexion réussie, échec, récupération
    assert metrics["tests_generated"] >= 3
    assert metrics["total_time"] > 0

    # Vérification des étapes
    steps = result["steps"]
    assert all(step["status"] == "success" for step in steps.values())

    # Vérification des fichiers générés
    excel_path = steps["matrix"]["file"]
    assert Path(excel_path).exists()

    # Vérification de la structure Excel
    import pandas as pd
    df = pd.read_excel(excel_path)
    assert len(df) >= 3
    assert "ID" in df.columns
    assert "Test_Code" in df.columns


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_with_pdf_sfd(full_orchestrator, tmp_path: Path):
    """Test avec un fichier PDF comme source SFD."""

    # Créer un mock de PDF (dans un vrai test, utiliser un vrai PDF)
    pdf_path = tmp_path / "specification.pdf"
    pdf_path.write_text("Ceci est une simulation de contenu PDF pour les tests")

    result = await full_orchestrator.process_sfd_to_tests(str(pdf_path))

    # Le pipeline devrait gérer le PDF via OCR
    assert "steps" in result
    assert "extraction" in result["steps"]
    assert result["steps"]["extraction"]["status"] in ["success", "error"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_error_handling(full_orchestrator, tmp_path: Path):
    """Test la gestion d'erreurs dans le pipeline."""

    # Test avec fichier corrompu
    corrupt_path = tmp_path / "corrupt.sfd"
    corrupt_path.write_text("Contenu corrompu ou illisible")

    result = await full_orchestrator.process_sfd_to_tests(str(corrupt_path))

    # Devrait retourner une erreur avec détails
    assert result["status"] == "error"
    assert "error" in result
    assert "error_type" in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_with_different_test_types(full_orchestrator, tmp_path: Path):
    """Test avec différents types de tests."""

    sfd_path = tmp_path / "api_sfd.txt"
    sfd_path.write_text("""
    # API Spécification
    ## Endpoint /api/login
    - Method: POST
    - Body: {email, password}
    - Response: {token, user_id}
    """)

    config = {
        "test_types": ["api"],
        "use_page_object": False
    }

    result = await full_orchestrator.process_sfd_to_tests(str(sfd_path), config)

    assert result["status"] == "completed"

    # Vérifier que les tests générés sont des tests API
    if "generated_tests" in result:
        for test in result["generated_tests"]:
            assert "requests.post" in test["code"] or "client.post" in test["code"]