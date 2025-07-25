# src/modules/psychodesign/personality_quiz.py
"""Module pour le quiz de personnalisation de l'IA Altiora.

Ce module permet de définir le profil initial de la personnalité de l'IA
en posant une série de questions à l'utilisateur. Il collecte des réponses
textuelles et peut potentiellement analyser des caractéristiques vocales
pour affiner les traits de personnalité de l'assistant QA.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Importation conditionnelle de speech_recognition.
try:
    import speech_recognition as sr
    HAS_SPEECH_RECOGNITION = True
except ImportError:
    sr = None
    HAS_SPEECH_RECOGNITION = False
    logging.warning("La bibliothèque 'speech_recognition' n'est pas installée. La calibration vocale sera désactivée.")

logger = logging.getLogger(__name__)


@dataclass
class QuizResponse:
    """Représente une réponse individuelle à une question du quiz."""
    question_id: str
    response: Any
    confidence: float
    response_time: float
    vocal_features: Dict[str, float]


@dataclass
class PersonalityProfile:
    """Représente le profil de personnalité complet de l'IA pour un utilisateur donné."""
    user_id: str
    traits: Dict[str, float] # Traits de personnalité (ex: formalité, empathie).
    preferences: Dict[str, Any] # Préférences de communication (ex: vouvoiement, expressions).
    vocal_profile: Dict[str, Any] # Caractéristiques vocales (si calibration effectuée).
    behavioral_patterns: Dict[str, Any] # Modèles comportementaux identifiés.
    quiz_metadata: Dict[str, Any] # Métadonnées du quiz (date de complétion, etc.).


class PersonalityQuiz:
    """Système de quiz de personnalisation avancé pour définir le profil de l'IA."""

    def __init__(self, user_id: str):
        """Initialise le quiz de personnalité."

        Args:
            user_id: L'identifiant de l'utilisateur qui passe le quiz.
        """
        self.user_id = user_id
        self.responses: List[QuizResponse] = []
        self.vocal_samples: List[Dict[str, Any]] = []

        self.quiz_path = Path("quiz_data") # Répertoire pour sauvegarder les données du quiz.
        self.quiz_path.mkdir(exist_ok=True)

        # Initialisation conditionnelle de speech recognition.
        self.recognizer: Optional[sr.Recognizer] = None
        self.microphone: Optional[sr.Microphone] = None
        if HAS_SPEECH_RECOGNITION:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()

        self.questions = self._load_questions()

    # ------------------------------------------------------------------
    # Questionnaire (définition des questions)
    # ------------------------------------------------------------------

    @staticmethod
    def _load_questions() -> List[Dict[str, Any]:
        """Charge la liste des questions du quiz."

        Returns:
            Une liste de dictionnaires, chaque dictionnaire représentant une question.
        """
        return [
            {
                "id": "comm_1",
                "type": "choice",
                "question": "Comment préférez-vous qu'on s'adresse à vous ?",
                "options": [
                    {"text": "Salut ! (familier)", "value": "tu", "weight": 0.2},
                    {"text": "Bonjour (professionnel)", "value": "vous", "weight": 0.8},
                    {"text": "S'adapte selon le contexte", "value": "adaptive", "weight": 0.5}
                ],
                "trait": "formalite"
            },
            {
                "id": "comm_2",
                "type": "scale",
                "question": "Quand j'explique quelque chose, préférez-vous :",
                "scale": {
                    "min": "Aller directement au résultat",
                    "max": "Avoir tous les détails et le contexte"
                },
                "trait": "verbosite"
            },
            {
                "id": "comm_3",
                "type": "scenario",
                "question": "Je viens de terminer une analyse complexe. Votre réaction préférée :",
                "options": [
                    {"text": "Parfait, donne-moi juste le résumé", "weight": 0.1},
                    {"text": "Super! Peux-tu m'expliquer les points clés ?", "weight": 0.5},
                    {"text": "Génial! J'aimerais comprendre tout le processus", "weight": 0.9}
                ],
                "trait": "verbosite"
            },
            {
                "id": "work_1",
                "type": "choice",
                "question": "Face à une erreur dans votre code, préférez-vous que je :",
                "options": [
                    {"text": "Corrige directement sans vous déranger", "weight": 0.0},
                    {"text": "Vous montre la correction avec explication rapide", "weight": 0.3},
                    {"text": "Explique le problème et vous guide vers la solution", "weight": 0.7},
                    {"text": "Fais une session complète de debugging ensemble", "weight": 1.0}
                ],
                "trait": "empathie"
            },
            {
                "id": "vocal_1",
                "type": "calibration",
                "question": "Lisez cette phrase : 'Altiora, analyse le document de spécification et crée les tests'",
                "purpose": "baseline"
            },
            {
                "id": "vocal_2",
                "type": "calibration",
                "question": "Lisez : 'Non, je voulais dire le module de paiement, pas le module utilisateur'",
                "purpose": "correction"
            },
            {
                "id": "vocal_3",
                "type": "calibration",
                "question": "Lisez : 'Parfait! Exactement ce que je voulais'",
                "purpose": "satisfaction"
            }
        ]

    async def start_quiz(self) -> PersonalityProfile:
        """Démarre le processus du quiz de personnalisation."

        Parcourt toutes les questions, collecte les réponses et génère le profil.

        Returns:
            L'objet `PersonalityProfile` généré.
        """
        logger.info(f"\nQuiz de personnalisation Altiora pour {self.user_id}")
        print("=" * 60)

        for question in self.questions:
            await self._ask_question(question)

        await self._analyze_vocal_patterns() # Analyse les patterns vocaux si des échantillons ont été collectés.
        profile = self._generate_profile()
        await self._save_profile(profile)
        return profile

    # ------------------------------------------------------------------
    # Gestionnaires de questions
    # ------------------------------------------------------------------

    async def _ask_question(self, question: Dict[str, Any]) -> None:
        """Pose une question à l'utilisateur et collecte sa réponse."

        Args:
            question: Le dictionnaire représentant la question à poser.
        """
        logger.info(f"\n{question['question']}")

        response: Dict[str, Any]
        if question["type"] == "choice":
            response = await self._handle_choice_question(question)
        elif question["type"] == "scale":
            response = await self._handle_scale_question(question)
        elif question["type"] == "calibration":
            response = await self._handle_calibration_question(question)
        else:
            response = await self._handle_text_question(question)

        self.responses.append(
            QuizResponse(
                question_id=question["id"],
                response=response["value"],
                confidence=response.get("confidence", 1.0),
                response_time=response.get("time", 0.0),
                vocal_features=response.get("vocal_features", {})
            )
        )

    @staticmethod
    async def _handle_choice_question(question: Dict[str, Any]) -> Dict[str, Any]:
        """Gère les questions à choix multiples."""
        for i, opt in enumerate(question["options"], 1):
            logger.info(f"  {i}. {opt['text']}")
        while True:
            try:
                choice = int(input("Votre choix (1-{}): ".format(len(question["options"]))).strip())
                if 1 <= choice <= len(question["options"]):
                    selected = question["options"][choice - 1]
                    return {"value": selected.get("value", selected["weight"])} # Retourne la valeur ou le poids.
                else:
                    logger.warning("Choix invalide. Veuillez entrer un nombre dans la plage indiquée.")
            except ValueError:
                logger.warning("Entrée invalide. Veuillez entrer un nombre.")

    @staticmethod
    async def _handle_scale_question(_question: Dict[str, Any]) -> Dict[str, Any]:
        """Gère les questions avec une échelle de valeur (ex: 0 à 1)."""
        while True:
            try:
                val_str = input("Entrez une valeur entre 0 et 1 : ").strip()
                val = float(val_str)
                if 0.0 <= val <= 1.0:
                    return {"value": val}
                else:
                    logger.warning("Valeur hors de la plage. Veuillez entrer un nombre entre 0 et 1.")
            except ValueError:
                logger.warning("Entrée invalide. Veuillez entrer un nombre.")

    @staticmethod
    async def _handle_text_question(_question: Dict[str, Any]) -> Dict[str, Any]:
        """Gère les questions nécessitant une réponse textuelle libre."""
        text = input("Réponse : ").strip()
        return {"value": text}

    async def _handle_calibration_question(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """Gère les questions de calibration vocale en utilisant `speech_recognition`."""
        if not self.recognizer or not self.microphone:
            logger.info("Module speech_recognition non disponible. Calibration vocale ignorée.")
            return {"value": "skipped", "confidence": 0.0, "vocal_features": {}}

        logger.info("\nCalibration vocale - Lisez la phrase après le signal. Appuyez sur Entrée quand prêt.")
        input("Appuyez sur Entrée quand prêt...")

        try:
            with self.microphone as source:
                logger.info("Réglage du bruit ambiant...")
                self.recognizer.adjust_for_ambient_noise(source)
                logger.info("Parlez maintenant...")
                audio = self.recognizer.listen(source, timeout=5) # Écoute pendant 5 secondes.

            text = self.recognizer.recognize_google(audio, language="fr-FR") # Utilise Google Speech Recognition.
            features = await self._extract_vocal_features(audio) # Extrait les caractéristiques vocales.
            self.vocal_samples.append({"text": text, "features": features, "purpose": question["purpose"]})
            logger.info(f"Transcription : \"{text}\"")
            return {"value": text, "confidence": 1.0, "vocal_features": features}
        except sr.UnknownValueError:
            logger.warning("Impossible de comprendre l'audio. Veuillez réessayer.")
            return await self._handle_calibration_question(question) # Demande de réessayer.
        except Exception as e:
            logger.error(f"Erreur lors de la calibration vocale : {e}")
            return {"value": "error", "confidence": 0.0, "vocal_features": {}}

    @staticmethod
    async def _extract_vocal_features(_audio: Any) -> Dict[str, float]:
        """Extrait les caractéristiques vocales à partir d'un échantillon audio (stub pour l'instant)."

        Args:
            _audio: L'objet audio enregistré.

        Returns:
            Un dictionnaire de caractéristiques vocales (ex: pitch, speed, volume).
        """
        # TODO: Implémenter une analyse vocale réelle pour extraire des caractéristiques.
        return {"pitch": 220.0, "speed": 150.0, "volume": 0.7, "stress_indicators": 0.2}

    # ------------------------------------------------------------------
    # Génération du profil de personnalité
    # ------------------------------------------------------------------

    async def _analyze_vocal_patterns(self) -> None:
        """Analyse les patterns vocaux collectés pour affiner le profil de personnalité (stub)."

        Cette méthode serait utilisée pour intégrer les données vocales dans le calcul des traits.
        """
        # TODO: Implémenter l'analyse des patterns vocaux.
        pass

    def _generate_profile(self) -> PersonalityProfile:
        """Génère le profil de personnalité complet basé sur les réponses du quiz et l'analyse vocale."""
        return PersonalityProfile(
            user_id=self.user_id,
            traits=self._calculate_traits(),
            preferences=self._analyze_preferences(),
            vocal_profile=self._create_vocal_profile(),
            behavioral_patterns=self._identify_patterns(),
            quiz_metadata={
                "completed_at": datetime.now().isoformat(),
                "question_count": len(self.responses),
                "calibration_samples": len(self.vocal_samples)
            }
        )

    def _calculate_traits(self) -> Dict[str, float]:
        """Calcule les traits de personnalité de l'IA basés sur les réponses du quiz."""
        # Valeurs par défaut des traits.
        traits = {
            "formalite": 0.6,
            "empathie": 0.7,
            "humor": 0.3,
            "proactivite": 0.5,
            "verbosite": 0.5,
            "confirmation": 0.3,
            "technical_level": 0.7
        }

        # Ajuste les traits en fonction des réponses du quiz.
        for response in self.responses:
            question_id = response.question_id
            value = response.response

            if question_id == "comm_1":
                if value == "tu":
                    traits["formalite"] = 0.2
                elif value == "vous":
                    traits["formalite"] = 0.8
                elif value == "adaptive":
                    traits["formalite"] = 0.5

            elif question_id == "comm_2" and isinstance(value, (int, float)):
                traits["verbosite"] = float(value)
            # TODO: Ajouter la logique pour d'autres questions et traits.

        return traits

    def _analyze_preferences(self) -> Dict[str, Any]:
        """Analyse les préférences utilisateur basées sur les réponses du quiz."""
        preferences = {
            "vouvoiement": True,
            "expressions": ["Parfait!", "Intéressant", "Voyons voir..."],
            "voice_settings": {"pitch": 1.0, "speed": 1.1, "intonation": "dynamique"}
        }

        for response in self.responses:
            if response.question_id == "comm_1" and response.response == "tu":
                preferences["vouvoiement"] = False
                preferences["expressions"] = ["Cool!", "OK", "Génial!"]
            # TODO: Ajouter la logique pour d'autres préférences.

        return preferences

    def _create_vocal_profile(self) -> Dict[str, Any]:
        """Crée le profil vocal basé sur les échantillons collectés."""
        if not self.vocal_samples:
            return {"status": "no_samples", "baseline": None}

        return {
            "samples": len(self.vocal_samples),
            "baseline": self.vocal_samples[0] if self.vocal_samples else None,
            "variations": self._analyze_vocal_variations() # Analyse les variations vocales.
        }

    def _analyze_vocal_variations(self) -> Dict[str, float]:
        """Analyse les variations vocales entre les échantillons (stub)."

        Cette méthode calculerait des métriques comme la variance du pitch, de la vitesse, etc.
        """
        if len(self.vocal_samples) < 2:
            return {}

        # TODO: Implémenter une analyse réelle des variations vocales.
        variations = {
            "pitch_variance": 0.1,
            "speed_variance": 0.05,
            "stress_change": 0.2
        }
        return variations

    def _identify_patterns(self) -> Dict[str, Any]:
        """Identifie les patterns comportementaux de l'utilisateur (stub)."

        Cette méthode analyserait les réponses pour déduire des habitudes ou préférences.
        """
        # TODO: Implémenter l'identification des patterns comportementaux.
        patterns = {
            "response_time_avg": sum(r.response_time for r in self.responses) / len(self.responses) if self.responses else 0,
            "confidence_avg": sum(r.confidence for r in self.responses) / len(self.responses) if self.responses else 0,
            "quiz_completion": True
        }
        return patterns

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------

    async def _save_profile(self, profile: PersonalityProfile) -> None:
        """Sauvegarde le profil de personnalité généré dans un fichier JSON."

        Args:
            profile: L'objet `PersonalityProfile` à sauvegarder.
        """
        try:
            self.quiz_path.mkdir(parents=True, exist_ok=True)
            profile_path = self.quiz_path / f"{self.user_id}_profile.json"

            with open(profile_path, "w", encoding="utf-8") as f:
                # `default=str` est utilisé pour sérialiser les objets `datetime` en chaînes.
                json.dump(asdict(profile), f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"\n✅ Profil de personnalité sauvegardé : {profile_path}")
        except (IOError, OSError) as e:
            logger.error(f"\n❌ Erreur lors de la sauvegarde du profil : {e}")

    # ------------------------------------------------------------------
    # Assistants
    # ------------------------------------------------------------------

    def get_progress(self) -> Dict[str, Any]:
        """Retourne la progression actuelle du quiz."

        Returns:
            Un dictionnaire contenant le nombre de questions complétées, le total,
            le pourcentage et la section courante.
        """
        return {
            "completed": len(self.responses),
            "total": len(self.questions),
            "percentage": (len(self.responses) / len(self.questions)) * 100.0 if len(self.questions) > 0 else 0.0,
            "current_section": self._get_current_section()
        }

    def _get_current_section(self) -> str:
        """Identifie la section courante du quiz basée sur la progression."""
        if not self.responses:
            return "Général"

        if len(self.responses) >= len(self.questions):
            return "Terminé"

        current_question = self.questions[len(self.responses)]
        section_map = {
            "comm": "Communication",
            "work": "Style de travail",
            "stress": "Gestion du stress",
            "humor": "Ton et humour",
            "tech": "Préférences techniques",
            "vocal": "Calibration vocale",
            "scenario": "Scénarios pratiques"
        }
        # Extrait le préfixe de l'ID de la question (ex: 'comm' de 'comm_1').
        return section_map.get(current_question["id"].split("_")[0], "Général")


class QuizReporter:
    """Génère des rapports textuels et des résumés des profils de personnalité."""

    @staticmethod
    def generate_summary(profile: PersonalityProfile) -> str:
        """Génère un résumé textuel concis du profil de personnalité."

        Args:
            profile: L'objet `PersonalityProfile` à résumer.

        Returns:
            Une chaîne de caractères formatée avec les traits et préférences clés.
        """
        traits = profile.traits
        prefs = profile.preferences

        summary = f"""
--- Rapport de Personnalisation Altiora ---
Utilisateur: {profile.user_id}
Date de complétion: {profile.quiz_metadata['completed_at']}

Traits principaux:
- Formalité: {traits['formalite']:.0%}
- Empathie: {traits['empathie']:.0%}
- Humour: {traits['humor']:.0%}
- Proactivité: {traits['proactivite']:.0%}
- Verbosité: {traits['verbosite']:.0%}
- Confirmation: {traits['confirmation']:.0%}
- Niveau technique: {traits['technical_level']:.0%}

Préférences:
- Vouvoiement: {'Oui' if prefs['vouvoiement'] else 'Non'}
- Expressions favorites: {', '.join(prefs['expressions'][:3])}

Profil vocal:
- Échantillons collectés: {profile.vocal_profile.get('samples', 0)}
- Statut: {profile.vocal_profile.get('status', 'Non calibré' if not profile.vocal_profile.get('samples') else 'Calibré')}
"""
        return summary


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def run_demo():
        quiz = PersonalityQuiz("demo_user")
        profile = await quiz.start_quiz()
        print(QuizReporter.generate_summary(profile))

        # Nettoyage des fichiers générés par la démo.
        quiz.quiz_path.unlink(missing_ok=True)

    asyncio.run(run_demo())