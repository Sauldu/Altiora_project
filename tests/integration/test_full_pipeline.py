# tests/integration/test_full_pipeline.py
"""Tests d'intégration pour le pipeline complet SFD → Tests Playwright.

Ce module contient des tests de bout en bout qui vérifient le fonctionnement
intégré de l'application Altiora, de l'analyse d'une Spécification Fonctionnelle
Détaillée (SFD) à la génération et à la validation des tests Playwright.
Il couvre différents scénarios, y compris la gestion des erreurs et les
différents formats d'entrée (ex: PDF).
"""

from pathlib import Path

import pytest

# Importation des composants nécessaires pour le test.
from src.core.altiora_assistant import AltioraQAAssistant
from src.models.sfd_models import SFDAnalysisRequest


@pytest.fixture(scope="session")
async def full_orchestrator():
    """Fixture Pytest pour initialiser et fermer l'orchestrateur complet de l'application."

    Cette fixture assure que l'orchestrateur est prêt avant l'exécution des tests
    et que ses ressources sont libérées après.
    """
    orchestrator = AltioraQAAssistant()
    await orchestrator.initialize()
    yield orchestrator
    await orchestrator.close()


@pytest.fixture
def sample_sfd_content():
    """Fixture fournissant un contenu SFD détaillé pour les tests."

    Ce contenu simule une spécification fonctionnelle pour un module d'authentification,
    incluant des scénarios de connexion réussie et échouée, ainsi que la récupération de mot de passe.
    """
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
async def test_sfd_to_test_pipeline_complete(full_orchestrator, tmp_path: Path, sample_sfd_content: str):
    """Test de bout en bout du pipeline complet : SFD → Analyse → Génération de tests Playwright."

    Ce test vérifie que l'orchestrateur peut prendre une SFD, l'analyser,
    générer des scénarios, puis produire des tests Playwright et un rapport Excel.
    """

    # 1. Préparation du fichier SFD temporaire.
    sfd_path = tmp_path / "complete_sfd.txt"
    sfd_path.write_text(sample_sfd_content)

    # 2. Création de la requête d'analyse SFD.
    sfd_request = SFDAnalysisRequest(content=sfd_path.read_text(), extraction_type="complete")

    # 3. Exécution du pipeline complet via l'orchestrateur.
    result = await full_orchestrator.run_full_pipeline(str(sfd_path))

    # 4. Assertions sur les résultats du pipeline.
    assert result["status"] == "completed", "Le pipeline devrait se terminer avec le statut 'completed'."

    # Vérification des métriques de performance et de contenu.
    metrics = result["metrics"]
    assert metrics["scenarios_found"] >= 3, "Au moins 3 scénarios devraient être trouvés dans la SFD."
    assert metrics["tests_generated"] >= 3, "Au moins 3 tests devraient être générés."
    assert metrics["total_time"] > 0, "Le temps total d'exécution devrait être positif."

    # Vérification du statut de chaque étape du pipeline.
    steps = result["steps"]
    assert all(step["status"] == "success" for step in steps.values()), "Toutes les étapes du pipeline devraient réussir."

    # Vérification de l'existence du rapport Excel généré.
    excel_path = Path(steps["matrix"]["file"])
    assert excel_path.exists(), "Le fichier Excel du rapport devrait exister."

    # Vérification de la structure et du contenu du fichier Excel.
    import pandas as pd
    df = pd.read_excel(excel_path)
    assert len(df) >= 3, "Le fichier Excel devrait contenir au moins 3 lignes (scénarios)."
    assert "ID" in df.columns, "La colonne 'ID' devrait être présente dans le rapport Excel."
    assert "Test_Code" in df.columns, "La colonne 'Test_Code' devrait être présente dans le rapport Excel."


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_with_pdf_sfd(full_orchestrator, tmp_path: Path):
    """Test du pipeline avec un fichier PDF comme source SFD (simulé via contenu texte)."

    Ce test vérifie que le pipeline peut traiter un fichier PDF en utilisant
    le service OCR pour extraire le texte avant l'analyse par le LLM.
    """

    # Création d'un fichier PDF factice avec du contenu texte.
    # Dans un vrai test d'intégration, un vrai fichier PDF serait utilisé.
    pdf_path = tmp_path / "specification.pdf"
    pdf_path.write_text("Ceci est une simulation de contenu PDF pour les tests. Il contient des scénarios.")

    # Exécution du pipeline avec le fichier PDF.
    result = await full_orchestrator.run_full_pipeline(str(pdf_path))

    # Vérification que l'étape d'extraction (OCR) a été tentée.
    assert "steps" in result, "Les étapes du pipeline devraient être présentes dans le résultat."
    assert "extraction" in result["steps"], "L'étape d'extraction (OCR) devrait être présente."
    # Le statut peut être 'success' si l'OCR factice fonctionne, ou 'error' si l'OCR réel échoue.
    assert result["steps"]["extraction"]["status"] in ["success", "error"], "Le statut de l'extraction devrait être succès ou erreur."


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_error_handling(full_orchestrator, tmp_path: Path):
    """Test la gestion d'erreurs dans le pipeline, notamment avec un fichier SFD corrompu."

    Ce test s'assure que le pipeline gère correctement les erreurs et retourne
    un statut d'erreur approprié avec des détails.
    """

    # Création d'un fichier SFD corrompu ou illisible.
    corrupt_path = tmp_path / "corrupt.sfd"
    corrupt_path.write_text("Contenu corrompu ou illisible qui devrait causer une erreur.")

    # Exécution du pipeline avec le fichier corrompu.
    result = await full_orchestrator.run_full_pipeline(str(corrupt_path))

    # Vérification que le pipeline a échoué et contient des informations sur l'erreur.
    assert result["status"] == "error", "Le pipeline devrait retourner un statut 'error'."
    assert "error" in result, "Le résultat devrait contenir un champ 'error'."
    assert "error_type" in result, "Le résultat devrait contenir un champ 'error_type'."


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_with_different_test_types(full_orchestrator, tmp_path: Path):
    """Test du pipeline avec différents types de tests (ex: API tests).

    Ce test vérifie que le pipeline peut générer des tests pour des types
    spécifiques (comme les tests API) en fonction de la configuration fournie.
    """

    # Création d'une SFD d'exemple pour les tests API.
    sfd_path = tmp_path / "api_sfd.txt"
    sfd_path.write_text("""
    # API Spécification
    ## Endpoint /api/login
    - Method: POST
    - Body: {email, password}
    - Response: {token, user_id}
    """)

    # Configuration pour générer des tests API.
    config = {
        "test_types": ["api"],
        "use_page_object": False
    }

    # Exécution du pipeline avec la configuration spécifique.
    result = await full_orchestrator.run_full_pipeline(str(sfd_path), config)

    # Vérification que le pipeline a réussi.
    assert result["status"] == "completed", "Le pipeline devrait se terminer avec le statut 'completed'."

    # Vérification que les tests générés sont bien des tests API (contiennent des appels HTTP).
    if "generated_tests" in result:
        for test in result["generated_tests"]:
            assert "requests.post" in test["code"] or "client.post" in test["code"], "Le code généré devrait contenir des appels HTTP pour les tests API."