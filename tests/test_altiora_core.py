# tests/test_altiora_core.py
"""Tests unitaires pour le noyau de personnalité AltioraCore.

Ce module contient des tests pour vérifier le bon fonctionnement des
composants centraux de la personnalité de l'IA, y compris le suivi de
l'évolution des traits et la création de propositions d'apprentissage.
"""

import pytest
import datetime
from unittest.mock import MagicMock
from src.modules.psychodesign.altiora_core import AltioraCore, PersonalityEvolution, LearningProposal
from src.modules.psychodesign.personality_quiz import PersonalityProfile # Import nécessaire pour la fixture.


@pytest.fixture
async def altiora_core():
    """Fixture Pytest pour initialiser une instance de `AltioraCore` pour les tests."

    Utilise un `MagicMock` pour simuler le `AdminControlSystem` afin d'isoler les tests.
    """
    # Crée un profil de personnalité par défaut pour le test.
    mock_personality_profile = PersonalityProfile(
        user_id="test_user",
        traits={
            "formalite": 0.5,
            "empathie": 0.5,
            "humor": 0.5,
            "proactivite": 0.5,
            "verbosite": 0.5,
            "confirmation": 0.5,
            "technical_level": 0.5,
        },
        preferences={},
        vocal_profile={},
        behavioral_patterns={},
        quiz_metadata={},
    )

    # Mocke le AdminControlSystem.
    mock_admin_system = MagicMock()
    mock_admin_system.execute_admin_command.return_value = {"status": "success"}

    core = AltioraCore("test_user", mock_admin_system)
    # Surcharge la personnalité par défaut avec le mock pour un état de test prévisible.
    core.personality = mock_personality_profile
    yield core


@pytest.mark.asyncio
async def test_personality_evolution_tracking(altiora_core: AltioraCore):
    """Teste que l'historique d'évolution de la personnalité est correctement suivi."

    Vérifie qu'un objet `PersonalityEvolution` est ajouté à l'historique
    et que ses valeurs sont correctes.
    """
    evolution = PersonalityEvolution(
        timestamp=datetime.datetime.now(),
        change_type="trait_formalite",
        old_value=0.5,
        new_value=0.7,
        reason="User feedback",
        source="learning"
    )

    altiora_core.evolution_history.append(evolution)
    assert len(altiora_core.evolution_history) == 1
    assert altiora_core.evolution_history[0].new_value == 0.7
    assert altiora_core.evolution_history[0].change_type == "trait_formalite"


@pytest.mark.asyncio
async def test_learning_proposal_creation(altiora_core: AltioraCore):
    """Teste la création d'une proposition d'apprentissage."

    Vérifie qu'un objet `LearningProposal` est correctement créé et ajouté
    à la liste des propositions en attente.
    """
    proposal = LearningProposal(
        proposal_id="test_001",
        user_id="test_user",
        suggested_changes={"empathie": 0.8},
        confidence_score=0.9,
        evidence=[{"type": "feedback"}],
        timestamp=datetime.datetime.now()
    )

    altiora_core.learning_proposals.append(proposal)
    assert len(altiora_core.learning_proposals) == 1
    assert proposal.suggested_changes["empathie"] == 0.8
    assert proposal.status == "pending"


@pytest.mark.asyncio
async def test_handle_correction_feedback(altiora_core: AltioraCore):
    """Teste le traitement d'un feedback de correction utilisateur."

    Vérifie que le système génère une proposition d'apprentissage basée sur
    le feedback de correction et la soumet à l'administrateur.
    """
    feedback = {
        "type": "correction",
        "original": "Hello, how are you doing today?",
        "corrected": "Hi!"
    }

    # Appelle la méthode qui traite le feedback.
    proposal = await altiora_core.process_learning_feedback(feedback)

    # Vérifie qu'une proposition a été créée.
    assert proposal is not None
    assert "verbosite" in proposal.suggested_changes # La verbosité devrait être ajustée.
    assert proposal.status == "pending"
    # Vérifie que la commande admin a été appelée.
    altiora_core.admin_system.execute_admin_command.assert_called_once()


@pytest.mark.asyncio
async def test_apply_approved_changes(altiora_core: AltioraCore):
    """Teste l'application des changements de personnalité après approbation administrative."

    Vérifie que les traits de personnalité sont mis à jour et que l'historique
    d'évolution est enregistré.
    """
    # Crée une proposition d'apprentissage et la marque comme approuvée.
    proposal_id = "approved_prop_001"
    approved_changes = {"formalite": 0.9, "empathie": 0.6}
    proposal = LearningProposal(
        proposal_id=proposal_id,
        user_id="test_user",
        suggested_changes=approved_changes,
        confidence_score=1.0,
        evidence=[],
        timestamp=datetime.datetime.now(),
        status="approved" # Statut approuvé.
    )
    altiora_core.learning_proposals.append(proposal)

    # Applique les changements.
    applied = await altiora_core.apply_approved_changes(proposal_id)

    assert applied is True
    assert altiora_core.personality.traits["formalite"] == 0.9
    assert altiora_core.personality.traits["empathie"] == 0.6
    assert len(altiora_core.evolution_history) == 2 # Deux changements de traits.
    assert altiora_core.evolution_history[0].approved is True


@pytest.mark.asyncio
async def test_get_personality_summary(altiora_core: AltioraCore):
    """Teste la génération du résumé de la personnalité."

    Vérifie que le résumé contient les informations clés du profil.
    """
    summary = altiora_core.get_personality_summary()
    assert summary["user_id"] == "test_user"
    assert "current_traits" in summary
    assert "evolution_count" in summary
    assert "pending_proposals" in summary


@pytest.mark.asyncio
async def test_get_evolution_report(altiora_core: AltioraCore):
    """Teste la génération du rapport textuel d'évolution."

    Vérifie que le rapport est formaté correctement et contient les informations
    essentielles sur les traits et l'historique.
    """
    report = altiora_core.get_evolution_report()
    assert "Rapport d'Évolution" in report
    assert "Traits actuels" in report
    assert "Historique" in report
