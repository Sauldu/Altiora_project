# tests/test_altiora_core.py
import pytest
import datetime
import asyncio
from unittest.mock import AsyncMock, MagicMock
from psychodesign.altiora_core import AltioraCore, PersonalityEvolution, LearningProposal


@pytest.fixture
async def altiora_core():
    core = AltioraCore("test_user", MagicMock())
    yield core


@pytest.mark.asyncio
async def test_personality_evolution_tracking(altiora_core):
    """Teste le suivi de l'évolution de la personnalité."""
    evolution = PersonalityEvolution(
        timestamp=datetime.now(),
        change_type="trait_formalite",
        old_value=0.5,
        new_value=0.7,
        reason="User feedback",
        source="learning"
    )

    altiora_core.evolution_history.append(evolution)
    assert len(altiora_core.evolution_history) == 1
    assert altiora_core.evolution_history[0].new_value == 0.7


@pytest.mark.asyncio
async def test_learning_proposal_creation(altiora_core):
    """Teste la création de propositions d'apprentissage."""
    proposal = LearningProposal(
        proposal_id="test_001",
        user_id="test_user",
        suggested_changes={"empathie": 0.8},
        confidence_score=0.9,
        evidence=[{"type": "feedback"}],
        timestamp=datetime.now()
    )

    altiora_core.learning_proposals.append(proposal)
    assert len(altiora_core.learning_proposals) == 1
    assert proposal.suggested_changes["empathie"] == 0.8


@pytest.mark.asyncio
async def test_handle_correction_feedback(altiora_core):
    """Teste le traitement des feedbacks de correction."""
    feedback = {
        "type": "correction",
        "original": "Hello",
        "corrected": "Bonjour"
    }

    proposal = await altiora_core.process_learning_feedback(feedback)
    assert proposal is not None
    assert proposal.change_type == "correction"