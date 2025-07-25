# tests/test_personality_quiz.py
import pytest
from unittest.mock import patch, MagicMock
from modules.psychodesign.personality_quiz import PersonalityQuiz


@pytest.fixture
def quiz():
    return PersonalityQuiz("test_user")


@pytest.mark.asyncio
async def test_quiz_initialization(quiz):
    """Test l'initialisation du quiz."""
    assert quiz.user_id == "test_user"
    assert len(quiz.questions) > 0


@pytest.mark.asyncio
@patch('builtins.input', return_value='1')
async def test_choice_question_handling(quiz):
    """Test le traitement des questions à choix multiples."""
    question = {
        "id": "test_choice",
        "type": "choice",
        "question": "Test?",
        "options": [{"text": "A", "weight": 0.1}, {"text": "B", "weight": 0.9}]
    }

    response = await quiz._handle_choice_question(question)
    assert response["value"] == 0.1


def test_personality_profile_generation(quiz):
    """Test la génération correcte du profil de personnalité."""
    # Simuler des réponses
    quiz.responses = [
        MagicMock(question_id="comm_1", response="vous", confidence=1.0),
        MagicMock(question_id="work_1", response=0.7, confidence=1.0)
    ]

    profile = quiz._generate_profile()
    assert profile.user_id == "test_user"
    assert "formalite" in profile.traits
    assert profile.traits["formalite"] > 0.5  # Car "vous" a été choisi