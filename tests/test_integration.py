# tests/test_integration.py
import pytest
import asyncio
from pathlib import Path
from src.orchestrator import Orchestrator


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_pipeline(tmp_path: Path):
    """Test complet du pipeline."""
    orchestrator = Orchestrator()

    try:
        await orchestrator.initialize()

        # Créer un SFD de test
        sfd_path = tmp_path / "integration_test.txt"
        sfd_path.write_text("""
        Spécification: Module de Login

        1. Connexion réussie
        - L'utilisateur entre email valide
        - L'utilisateur entre mot de passe valide
        - Le système redirige vers dashboard

        2. Échec de connexion
        - L'utilisateur entre mot de passe incorrect
        - Le système affiche une erreur
        """)

        result = await orchestrator.process_sfd_to_tests(str(sfd_path))

        assert result["status"] == "completed"
        assert result["metrics"]["scenarios_found"] >= 2
        assert result["metrics"]["tests_generated"] >= 2

    finally:
        await orchestrator.close()