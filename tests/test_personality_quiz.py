# tests/test_personality_quiz.py
"""Tests unitaires pour le module `PersonalityQuiz`.

Ce module contient des tests pour vérifier le bon fonctionnement du quiz de
personnalisation de l'IA, y compris l'initialisation, le traitement des
questions à choix multiples et la génération du profil de personnalité.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.modules.psychodesign.personality_quiz import PersonalityQuiz, QuizResponse, PersonalityProfile
from datetime import datetime


@pytest.fixture
def quiz():
    """Fixture pour une instance de `PersonalityQuiz` pour les tests."

    Initialise le quiz avec un utilisateur de test et des mocks pour les
    dépendances externes comme `speech_recognition`.
    """
    # Mocke les dépendances de speech_recognition si elles ne sont pas disponibles.
    with patch('src.modules.psychodesign.personality_quiz.sr') as mock_sr:
        mock_sr.Recognizer.return_value = MagicMock()
        mock_sr.Microphone.return_value = MagicMock()
        mock_sr.UnknownValueError = type('UnknownValueError', (Exception,), {})
        return PersonalityQuiz("test_user")


@pytest.mark.asyncio
async def test_quiz_initialization(quiz: PersonalityQuiz):
    """Teste l'initialisation correcte du quiz de personnalité."

    Vérifie que l'ID utilisateur est correctement défini et que les questions
    sont chargées.
    """
    assert quiz.user_id == "test_user"
    assert len(quiz.questions) > 0
    assert quiz.recognizer is not None # Vérifie que le mock est bien initialisé.


@pytest.mark.asyncio
@patch('builtins.input', return_value='1')
async def test_choice_question_handling(mock_input: MagicMock, quiz: PersonalityQuiz):
    """Teste le traitement des questions à choix multiples."

    Simule une réponse utilisateur et vérifie que la valeur correcte est retournée.
    """
    question = {
        "id": "test_choice",
        "type": "choice",
        "question": "Test?",
        "options": [{"text": "A", "weight": 0.1}, {"text": "B", "weight": 0.9}]
    }

    response = await quiz._handle_choice_question(question)
    assert response["value"] == 0.1
    mock_input.assert_called_once() # Vérifie que `input()` a été appelé.


@pytest.mark.asyncio
@patch('builtins.input', return_value='0.75')
async def test_scale_question_handling(mock_input: MagicMock, quiz: PersonalityQuiz):
    """Teste le traitement des questions à échelle."

    Simule une réponse numérique et vérifie que la valeur est correctement traitée.
    """
    question = {
        "id": "test_scale",
        "type": "scale",
        "question": "Évaluez de 0 à 1 :",
        "scale": {"min": "Faible", "max": "Fort"}
    }
    response = await quiz._handle_scale_question(question)
    assert response["value"] == 0.75
    mock_input.assert_called_once()


@pytest.mark.asyncio
@patch('builtins.input', return_value='Ceci est une réponse textuelle.')
async def test_text_question_handling(mock_input: MagicMock, quiz: PersonalityQuiz):
    """Teste le traitement des questions textuelles."

    Vérifie que la réponse textuelle est capturée correctement.
    """
    question = {"id": "test_text", "type": "text", "question": "Décrivez..."}
    response = await quiz._handle_text_question(question)
    assert response["value"] == "Ceci est une réponse textuelle."
    mock_input.assert_called_once()


@pytest.mark.asyncio
async def test_calibration_question_handling_success(quiz: PersonalityQuiz):
    """Teste le traitement d'une question de calibration vocale en cas de succès."

    Mocke `speech_recognition` pour simuler une transcription réussie.
    """
    if not quiz.recognizer: # Skip si speech_recognition n'est pas mocké.
        pytest.skip("Speech recognition not mocked.")

    # Mocke les méthodes de speech_recognition.
    quiz.recognizer.adjust_for_ambient_noise = MagicMock()
    quiz.recognizer.listen = AsyncMock(return_value=MagicMock())
    quiz.recognizer.recognize_google = MagicMock(return_value="Phrase de test vocale.")
    
    # Mocke la fonction _extract_vocal_features.
    with patch.object(quiz, '_extract_vocal_features', new_callable=AsyncMock) as mock_extract_vocal_features:
        mock_extract_vocal_features.return_value = {"pitch": 1.0, "speed": 1.0}

        question = {"id": "vocal_test", "type": "calibration", "question": "Lisez ceci.", "purpose": "test"}
        response = await quiz._handle_calibration_question(question)

        assert response["value"] == "Phrase de test vocale."
        assert response["confidence"] == 1.0
        assert "pitch" in response["vocal_features"]
        assert len(quiz.vocal_samples) == 1
        quiz.recognizer.adjust_for_ambient_noise.assert_called_once()
        quiz.recognizer.listen.assert_called_once()
        quiz.recognizer.recognize_google.assert_called_once()


@pytest.mark.asyncio
async def test_calibration_question_handling_failure(quiz: PersonalityQuiz):
    """Teste le traitement d'une question de calibration vocale en cas d'échec de reconnaissance."

    Simule une `UnknownValueError` de `speech_recognition`.
    """
    if not quiz.recognizer:
        pytest.skip("Speech recognition not mocked.")

    quiz.recognizer.adjust_for_ambient_noise = MagicMock()
    quiz.recognizer.listen = AsyncMock(side_effect=quiz.recognizer.UnknownValueError("Could not understand audio"))
    
    # Patch builtins.input pour éviter l'interaction utilisateur dans le retry.
    with patch('builtins.input', side_effect=['' for _ in range(2)]) as mock_input_retry:
        question = {"id": "vocal_test_fail", "type": "calibration", "question": "Lisez ceci.", "purpose": "test"}
        response = await quiz._handle_calibration_question(question)

        assert response["value"] == "error" # Ou un autre statut d'erreur.
        assert response["confidence"] == 0.0
        assert len(quiz.vocal_samples) == 0
        quiz.recognizer.listen.assert_called_once()


def test_personality_profile_generation(quiz: PersonalityQuiz):
    """Teste la génération correcte du profil de personnalité à partir des réponses du quiz."

    Vérifie que les traits et préférences sont calculés et stockés correctement.
    """
    # Simule des réponses pour le quiz.
    quiz.responses = [
        QuizResponse(question_id="comm_1", response="vous", confidence=1.0, response_time=1.0, vocal_features={}),
        QuizResponse(question_id="comm_2", response=0.7, confidence=1.0, response_time=1.0, vocal_features={}),
        QuizResponse(question_id="work_1", response=0.3, confidence=1.0, response_time=1.0, vocal_features={}),
    ]

    profile = quiz._generate_profile()
    assert profile.user_id == "test_user"
    assert "formalite" in profile.traits
    assert profile.traits["formalite"] == 0.8 # Basé sur la réponse "vous".
    assert profile.traits["verbosite"] == 0.7 # Basé sur la réponse 0.7.
    assert profile.traits["empathie"] == 0.3 # Basé sur la réponse 0.3.
    assert profile.preferences["vouvoiement"] is True
    assert "completed_at" in profile.quiz_metadata


@pytest.mark.asyncio
async def test_save_profile(quiz: PersonalityQuiz, tmp_path: Path):
    """Teste la sauvegarde du profil de personnalité sur le disque."

    Vérifie que le fichier JSON du profil est créé et contient les bonnes données.
    """
    # Surcharge le chemin de sauvegarde pour utiliser un répertoire temporaire.
    quiz.quiz_path = tmp_path / "quiz_data_temp"
    quiz.quiz_path.mkdir()

    profile = PersonalityProfile(
        user_id="save_test_user",
        traits={"formalite": 0.5},
        preferences={},
        vocal_profile={},
        behavioral_patterns={},
        quiz_metadata={'completed_at': datetime.now().isoformat()}
    )

    await quiz._save_profile(profile)

    saved_file = quiz.quiz_path / "save_test_user_profile.json"
    assert saved_file.exists()
    
    with open(saved_file, 'r', encoding='utf-8') as f:
        loaded_data = json.load(f)
    assert loaded_data["user_id"] == "save_test_user"
    assert loaded_data["traits"]["formalite"] == 0.5


def test_get_progress(quiz: PersonalityQuiz):
    """Teste la fonction de suivi de la progression du quiz."

    Vérifie que le pourcentage de complétion et la section courante sont corrects.
    """
    # Quiz vide.
    progress_empty = quiz.get_progress()
    assert progress_empty["completed"] == 0
    assert progress_empty["percentage"] == 0.0
    assert progress_empty["current_section"] == "Général"

    # Simule quelques réponses.
    quiz.responses.append(QuizResponse(question_id="comm_1", response="tu", confidence=1.0, response_time=1.0, vocal_features={}))
    progress_partial = quiz.get_progress()
    assert progress_partial["completed"] == 1
    assert progress_partial["percentage"] > 0.0
    assert progress_partial["current_section"] == "Communication" # Ou la section de la question suivante.

    # Simule la complétion du quiz.
    quiz.responses = [QuizResponse(question_id=q["id"], response="mock", confidence=1.0, response_time=1.0, vocal_features={}) for q in quiz.questions]
    progress_complete = quiz.get_progress()
    assert progress_complete["completed"] == len(quiz.questions)
    assert progress_complete["percentage"] == 100.0
    assert progress_complete["current_section"] == "Terminé"