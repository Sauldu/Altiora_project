# tests/test_integration.py
"""Tests d'intégration de haut niveau pour le pipeline principal d'Altiora.

Ce module contient des tests qui vérifient le fonctionnement de bout en bout
du pipeline SFD → Analyse → Génération de tests. Il s'assure que les
composants interagissent correctement et que le résultat final est conforme
aux attentes.
"""

import pytest
import asyncio
from pathlib import Path

from src.orchestrator import Orchestrator
from src.models.sfd_models import SFDAnalysisRequest # Import nécessaire pour SFDAnalysisRequest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_pipeline(tmp_path: Path):
    """Teste le pipeline complet de l'analyse SFD à la génération de tests."

    Ce test simule le processus de prise d'une SFD, son analyse par l'orchestrateur,
    et la vérification que des scénarios et des tests sont générés.

    Args:
        tmp_path: Fixture Pytest fournissant un répertoire temporaire pour les fichiers.
    """
    orchestrator = Orchestrator() # Crée une instance de l'orchestrateur.

    try:
        await orchestrator.initialize() # Initialise l'orchestrateur.

        # Crée un fichier SFD de test temporaire.
        sfd_content = """
        Spécification: Module de Login

        1. Connexion réussie
        - L'utilisateur entre email valide
        - L'utilisateur entre mot de passe valide
        - Le système redirige vers dashboard

        2. Échec de connexion
        - L'utilisateur entre mot de passe incorrect
        - Le système affiche une erreur
        """
        sfd_path = tmp_path / "integration_test.txt"
        sfd_path.write_text(sfd_content)

        # Crée une requête SFDAnalysisRequest.
        sfd_request = SFDAnalysisRequest(content=sfd_path.read_text())

        # Exécute le pipeline complet.
        result = await orchestrator.process_sfd_to_tests(sfd_request)

        # Assertions sur le résultat.
        assert result["status"] == "completed", "Le pipeline devrait se terminer avec le statut 'completed'."
        assert result["metrics"]["scenarios_found"] >= 2, "Au moins 2 scénarios devraient être trouvés."
        assert result["metrics"]["tests_generated"] >= 2, "Au moins 2 tests devraient être générés."

    finally:
        await orchestrator.close() # S'assure que l'orchestrateur est fermé.
