"""
Quiz de personnalisation pour Altiora - Assistant QA Personnel
- Définit le profil QA complet: analyseur, générateur, superviseur
- """

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

try:
    import speech_recognition as sr

    HAS_SPEECH_RECOGNITION = True
except ImportError:
    sr = None
    HAS_SPEECH_RECOGNITION = False


@dataclass
class QuizResponse:
    question_id: str
    response: Any
    confidence: float
    response_time: float
    vocal_features: Dict[str, float]


@dataclass
class PersonalityProfile:
    user_id: str
    traits: Dict[str, float]
    preferences: Dict[str, Any]
    vocal_profile: Dict[str, Any]
    behavioral_patterns: Dict[str, Any]
    quiz_metadata: Dict[str, Any]


class PersonalityQuiz:
    """Système de quiz de personnalisation avancé"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.responses: List[QuizResponse] = []
        self.vocal_samples: List[Dict[str, Any]] = []

        self.quiz_path = Path("quiz_data")
        self.quiz_path.mkdir(exist_ok=True)

        # Initialisation conditionnelle de speech recognition
        if sr:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
        else:
            self.recognizer = None
            self.microphone = None

        self.questions = self._load_questions()

    # ------------------------------------------------------------------
    # Questionnaire
    # ------------------------------------------------------------------

    @staticmethod
    def _load_questions() -> List[Dict[str, Any]]:
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
        print(f"\nQuiz de personnalisation Altiora pour {self.user_id}")
        print("=" * 60)

        for question in self.questions:
            await self._ask_question(question)

        await self._analyze_vocal_patterns()
        profile = self._generate_profile()
        await self._save_profile(profile)
        return profile

    # ------------------------------------------------------------------
    # Question handlers
    # ------------------------------------------------------------------

    async def _ask_question(self, question: Dict[str, Any]) -> None:
        print(f"\n{question['question']}")

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
        for i, opt in enumerate(question["options"], 1):
            print(f"  {i}. {opt['text']}")
        while True:
            try:
                choice = int(input("Votre choix (1-{}): ".format(len(question["options"]))))
                if 1 <= choice <= len(question["options"]):
                    selected = question["options"][choice - 1]
                    return {"value": selected.get("value", selected["weight"])}
            except ValueError:
                print("Choix invalide")

    @staticmethod
    async def _handle_scale_question(_question: Dict[str, Any]) -> Dict[str, Any]:
        val = float(input("Entrez une valeur entre 0 et 1 : "))
        return {"value": max(0.0, min(1.0, val))}

    @staticmethod
    async def _handle_text_question(_question: Dict[str, Any]) -> Dict[str, Any]:
        text = input("Réponse : ")
        return {"value": text}

    async def _handle_calibration_question(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """Gère les questions de calibration vocale"""
        if not self.recognizer or not self.microphone:
            print("Module speech_recognition non disponible, skip calibration vocale")
            return {"value": "skipped", "confidence": 0.0, "vocal_features": {}}

        print("\nCalibration vocale - Parlez après le signal")
        input("Appuyez sur Entrée quand prêt...")

        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source)
                audio = self.recognizer.listen(source, timeout=5)

            text = self.recognizer.recognize_google(audio, language="fr-FR")
            features = await self._extract_vocal_features(audio)
            self.vocal_samples.append({"text": text, "features": features, "purpose": question["purpose"]})
            return {"value": text, "confidence": 1.0, "vocal_features": features}
        except sr.UnknownValueError:
            print("Je n'ai pas compris, réessayez...")
            return await self._handle_calibration_question(question)
        except Exception as e:
            print(f"Erreur lors de la calibration vocale: {e}")
            return {"value": "error", "confidence": 0.0, "vocal_features": {}}

    @staticmethod
    async def _extract_vocal_features(_audio) -> Dict[str, float]:
        """Extrait les caractéristiques vocales (stub pour l'instant)"""
        return {"pitch": 220.0, "speed": 150.0, "volume": 0.7, "stress_indicators": 0.2}

    # ------------------------------------------------------------------
    # Profile generation
    # ------------------------------------------------------------------

    async def _analyze_vocal_patterns(self) -> None:
        """Analyse les patterns vocaux collectés"""
        pass  # Implementation future

    def _generate_profile(self) -> PersonalityProfile:
        """Génère le profil de personnalité basé sur les réponses"""
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
        """Calcule les traits de personnalité basés sur les réponses"""
        traits = {
            "formalite": 0.6,
            "empathie": 0.7,
            "humor": 0.3,
            "proactivite": 0.5,
            "verbosite": 0.5,
            "confirmation": 0.3,
            "technical_level": 0.7
        }

        # Analyse des réponses pour ajuster les traits
        for response in self.responses:
            question_id = response.question_id
            value = response.response

            # Ajustement basé sur les réponses
            if question_id == "comm_1":
                if value == "tu":
                    traits["formalite"] = 0.2
                elif value == "vous":
                    traits["formalite"] = 0.8
                elif value == "adaptive":
                    traits["formalite"] = 0.5

            elif question_id == "comm_2" and isinstance(value, (int, float)):
                traits["verbosite"] = float(value)

        return traits

    def _analyze_preferences(self) -> Dict[str, Any]:
        """Analyse les préférences utilisateur"""
        preferences = {
            "vouvoiement": True,
            "expressions": ["Parfait!", "Intéressant", "Voyons voir..."],
            "voice_settings": {"pitch": 1.0, "speed": 1.1, "intonation": "dynamique"}
        }

        # Ajuster selon les réponses
        for response in self.responses:
            if response.question_id == "comm_1" and response.response == "tu":
                preferences["vouvoiement"] = False
                preferences["expressions"] = ["Cool!", "OK", "Génial!"]

        return preferences

    def _create_vocal_profile(self) -> Dict[str, Any]:
        """Crée le profil vocal basé sur les échantillons"""
        if not self.vocal_samples:
            return {"status": "no_samples", "baseline": None}

        return {
            "samples": len(self.vocal_samples),
            "baseline": self.vocal_samples[0] if self.vocal_samples else None,
            "variations": self._analyze_vocal_variations()
        }

    def _analyze_vocal_variations(self) -> Dict[str, float]:
        """Analyse les variations vocales entre les échantillons"""
        if len(self.vocal_samples) < 2:
            return {}

        # Analyse basique des variations
        variations = {
            "pitch_variance": 0.1,
            "speed_variance": 0.05,
            "stress_change": 0.2
        }
        return variations

    def _identify_patterns(self) -> Dict[str, Any]:
        """Identifie les patterns comportementaux"""
        patterns = {
            "response_time_avg": sum(r.response_time for r in self.responses) / len(self.responses) if self.responses else 0,
            "confidence_avg": sum(r.confidence for r in self.responses) / len(self.responses) if self.responses else 0,
            "quiz_completion": True
        }
        return patterns

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _save_profile(self, profile: PersonalityProfile) -> None:
        """Sauvegarde le profil de personnalité"""
        try:
            self.quiz_path.mkdir(parents=True, exist_ok=True)
            profile_path = self.quiz_path / f"{self.user_id}_profile.json"

            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(asdict(profile), f, indent=2, ensure_ascii=False, default=str)

            print(f"\n✅ Profil sauvegardé: {profile_path}")
        except (IOError, OSError) as e:
            print(f"\n❌ Erreur lors de la sauvegarde du profil: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_progress(self) -> Dict[str, Any]:
        """Retourne la progression du quiz"""
        return {
            "completed": len(self.responses),
            "total": len(self.questions),
            "percentage": (len(self.responses) / len(self.questions)) * 100.0,
            "current_section": self._get_current_section()
        }

    def _get_current_section(self) -> str:
        """Identifie la section courante du quiz"""
        if not self.responses:
            return "Général"

        if len(self.responses) >= len(self.questions):
            return "Terminé"

        current = self.questions[len(self.responses)]
        section_map = {
            "comm": "Communication",
            "work": "Style de travail",
            "stress": "Gestion du stress",
            "humor": "Ton et humour",
            "tech": "Préférences techniques",
            "vocal": "Calibration vocale",
            "scenario": "Scénarios pratiques"
        }
        return section_map.get(current["id"].split("_")[0], "Général")


class QuizReporter:
    """Génère des rapports de personnalisation"""

    @staticmethod
    def generate_summary(profile: PersonalityProfile) -> str:
        """Génère un résumé du profil de personnalité"""
        traits = profile.traits
        prefs = profile.preferences

        return f"""
Rapport de Personnalisation Altiora
Utilisateur: {profile.user_id}
Date: {profile.quiz_metadata['completed_at']}

Traits principaux:
- Formalité: {traits['formalite']:.0%}
- Empathie: {traits['empathie']:.0%}
- Humour: {traits['humor']:.0%}
- Proactivité: {traits['proactivite']:.0%}
- Verbosité: {traits['verbosite']:.0%}

Préférences:
- Vouvoiement: {'Oui' if prefs['vouvoiement'] else 'Non'}
- Expressions favorites: {', '.join(prefs['expressions'][:3])}

Profil vocal:
- Échantillons collectés: {profile.vocal_profile.get('samples', 0)}
- Statut: {profile.vocal_profile.get('status', 'Complet')}
"""


# ------------------------------------------------------------------
# Quick test
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio


    async def run_demo():
        quiz = PersonalityQuiz("demo_user")
        profile = await quiz.start_quiz()
        print(QuizReporter.generate_summary(profile))


    asyncio.run(run_demo())
