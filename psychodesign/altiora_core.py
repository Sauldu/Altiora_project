"""
AltioraCore – Noyau de personnalité et d’apprentissage supervisé
Responsabilités :
- Gestion des traits de personnalité
- Apprentissage supervisé via feedback utilisateur
- Évolution contrôlée avec validation admin
- Historique et traçabilité des changements
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np

from guardrails.admin_control_system import AdminControlSystem, AdminCommand
from guardrails.ethical_safeguards import EthicalSafeguards
from psychodesign.personality_quiz import PersonalityProfile


@dataclass
class PersonalityEvolution:
    """Enregistrement d’un changement de personnalité"""
    timestamp: datetime
    change_type: str
    old_value: float
    new_value: float
    reason: str
    source: str  # auto, user_feedback, admin_override
    approved: bool = False
    admin_review: Optional[str] = None


@dataclass
class LearningProposal:
    """Proposition de modification supervisée"""
    proposal_id: str
    user_id: str
    suggested_changes: Dict[str, Any]
    confidence_score: float
    evidence: List[Dict[str, Any]]
    timestamp: datetime
    status: str = "pending"
    admin_decision: Optional[str] = None


class AltioraCore:
    """Moteur de personnalité avec apprentissage supervisé"""

    def __init__(self, user_id: str, admin_system: AdminControlSystem):
        self.user_id = user_id
        self.admin_system = admin_system
        self.ethical_safeguards = EthicalSafeguards()

        self.core_path = Path("altiora_core")
        self.core_path.mkdir(exist_ok=True)

        self.personality = self._load_default_personality()
        self.evolution_history: List[PersonalityEvolution] = []
        self.learning_proposals: List[LearningProposal] = []

        self.supervised_mode = False
        self.learning_mode = "conservative"
        self.logger = self._setup_logging()

    # ------------------------------------------------------------------
    # Initialisation & Persistence
    # ------------------------------------------------------------------

    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger(f"altiora_core_{self.user_id}")
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(self.core_path / f"{self.user_id}.log")
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
        return logger

    def _load_default_personality(self) -> PersonalityProfile:
        profile_file = self.core_path / f"{self.user_id}_profile.json"
        if profile_file.exists():
            with open(profile_file) as f:
                data = json.load(f)
                return PersonalityProfile(**data)

        return PersonalityProfile(
            user_id=self.user_id,
            traits={
                "formalite": 0.6,
                "empathie": 0.7,
                "humor": 0.2,
                "proactivite": 0.5,
                "verbosite": 0.5,
                "confirmation": 0.3,
                "technical_level": 0.7,
            },
            preferences={
                "vouvoiement": True,
                "expressions": ["Parfait!", "Intéressant", "Voyons voir..."],
                "voice_settings": {"pitch": 1.0, "speed": 1.1, "intonation": "dynamique"},
            },
            vocal_profile={},
            behavioral_patterns={},
            quiz_metadata={"created_at": datetime.now().isoformat()},
        )

    # ------------------------------------------------------------------
    # API Publique – Interaction & Apprentissage
    # ------------------------------------------------------------------

    async def process_learning_feedback(self, feedback: Dict[str, Any]) -> Optional[LearningProposal]:
        """Traite un feedback utilisateur et crée une proposition d’apprentissage"""
        feedback_type = feedback.get("type")
        if feedback_type == "correction":
            return await self._handle_correction_feedback(feedback)
        if feedback_type == "adjustment":
            return await self._handle_adjustment_feedback(feedback)
        if feedback_type == "explicit_preference":
            return await self._handle_preference_feedback(feedback)
        return None

    async def handle_user_interaction(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse éthique + réponse personnalisée"""
        alert = await self.ethical_safeguards.analyze_interaction(self.user_id, interaction)
        if alert and alert.severity == "critical":
            return {
                "status": "blocked",
                "message": "Interaction bloquée pour raisons éthiques",
                "alert_id": alert.alert_id,
            }

        response = await self._generate_response()
        if interaction.get("type") == "feedback":
            proposal = await self.process_learning_feedback(interaction)
            if proposal:
                response["learning_proposal"] = proposal.proposal_id

        self.logger.info("Interaction traitée : %s", interaction.get("type"))
        return response

    # ------------------------------------------------------------------
    # Gestion des Propositions
    # ------------------------------------------------------------------

    async def _handle_correction_feedback(self, feedback: Dict[str, Any]) -> Optional[LearningProposal]:
        original = feedback.get("original")
        corrected = feedback.get("corrected")
        changes = self._analyze_correction_impact(original, corrected)
        if not changes:
            return None

        proposal = LearningProposal(
            proposal_id=f"corr_{self.user_id}_{datetime.now().isoformat()}",
            user_id=self.user_id,
            suggested_changes=changes,
            confidence_score=0.9,
            evidence=[{"type": "correction", "data": feedback}],
            timestamp=datetime.now(),
        )
        self.learning_proposals.append(proposal)
        await self._submit_for_admin_review(proposal)
        return proposal

    async def _handle_adjustment_feedback(self, feedback: Dict[str, Any]) -> Optional[LearningProposal]:
        adjustment_type = feedback.get("adjustment_type")
        trait_map = {
            "shorter": ("verbosite", -0.2),
            "longer": ("verbosite", 0.2),
            "more_formal": ("formalite", 0.1),
            "less_formal": ("formalite", -0.1),
            "more_empathetic": ("empathie", 0.1),
            "less_empathetic": ("empathie", -0.1),
        }
        if adjustment_type not in trait_map:
            return None

        trait, delta = trait_map[adjustment_type]
        new_value = max(0.0, min(1.0, self.personality.traits[trait] + delta))

        proposal = LearningProposal(
            proposal_id=f"adj_{self.user_id}_{datetime.now().isoformat()}",
            user_id=self.user_id,
            suggested_changes={trait: new_value},
            confidence_score=0.7,
            evidence=[{"type": "adjustment", "data": feedback}],
            timestamp=datetime.now(),
        )
        self.learning_proposals.append(proposal)
        await self._submit_for_admin_review(proposal)
        return proposal

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _analyze_correction_impact(self, original: Optional[str], corrected: Optional[str]) -> Dict[str, float]:
        changes: Dict[str, float] = {}
        if not original or not corrected:
            return changes

        if len(corrected) < len(original) * 0.8:
            changes["verbosite"] = max(0.0, self.personality.traits["verbosite"] - 0.1)

        formal_indicators = ["vous", "monsieur", "madame"]
        orig_formal = any(w in str(original).lower() for w in formal_indicators)
        corr_formal = any(w in str(corrected).lower() for w in formal_indicators)
        if orig_formal != corr_formal:
            delta = 0.1 if corr_formal else -0.1
            changes["formalite"] = max(0.0, min(1.0, self.personality.traits["formalite"] + delta))
        return changes

    async def _submit_for_admin_review(self, proposal: LearningProposal) -> None:
        command = AdminCommand(
            command_id=proposal.proposal_id,
            timestamp=datetime.now(),
            action="review_learning_proposal",
            target_user=self.user_id,
            parameters={"proposal": asdict(proposal)},
        )
        await self.admin_system.execute_admin_command(command)
        self.logger.info("Proposition soumise : %s", proposal.proposal_id)

    async def _generate_response(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "response": "Réponse générée selon la personnalité actuelle",
            "personality_snapshot": self.personality.traits,
        }

    async def apply_approved_changes(self, proposal_id: str) -> bool:
        """Applique les changements validés par l’admin"""
        proposal = next((p for p in self.learning_proposals if p.proposal_id == proposal_id), None)
        if not proposal or proposal.status != "approved":
            return False

        for trait, new_value in proposal.suggested_changes.items():
            old_value = self.personality.traits.get(trait, 0.5)
            evolution = PersonalityEvolution(
                timestamp=datetime.now(),
                change_type=f"trait_{trait}",
                old_value=old_value,
                new_value=float(new_value),
                reason=f"Learning proposal {proposal_id}",
                source="learning",
                approved=True,
            )
            self.evolution_history.append(evolution)
            self.personality.traits[trait] = float(new_value)

        await self._save_state()
        self.logger.info("Changements appliqués : %s", proposal.suggested_changes)
        return True

    async def _save_state(self) -> None:
        """Sauvegarde l’état complet (personnalité + historique)"""
        with open(self.core_path / f"{self.user_id}_profile.json", "w") as f:
            json.dump(asdict(self.personality), f, indent=2, default=str)
        with open(self.core_path / f"{self.user_id}_evolution.json", "w") as f:
            json.dump([asdict(e) for e in self.evolution_history], f, indent=2, default=str)
        with open(self.core_path / f"{self.user_id}_proposals.json", "w") as f:
            json.dump([asdict(p) for p in self.learning_proposals], f, indent=2, default=str)

    # ------------------------------------------------------------------
    # Accès en lecture
    # ------------------------------------------------------------------

    def get_personality_summary(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "current_traits": self.personality.traits,
            "evolution_count": len(self.evolution_history),
            "pending_proposals": len([p for p in self.learning_proposals if p.status == "pending"]),
            "last_change": self.evolution_history[-1].timestamp if self.evolution_history else None,
            "supervised_mode": self.supervised_mode,
            "learning_mode": self.learning_mode,
        }

    def get_evolution_report(self) -> str:
        """Rapport textuel de l’évolution"""
        lines = [f"📈 **Rapport d'Évolution - {self.user_id}**", "", "**Traits actuels :**"]
        lines.extend(f"• {k} : {v:.1%}" for k, v in self.personality.traits.items())
        lines += [
            "",
            f"**Historique :** {len(self.evolution_history)} changements",
            f"**Propositions en attente :** {len([p for p in self.learning_proposals if p.status == 'pending'])}",
            f"**Mode apprentissage :** {self.learning_mode}",
        ]
        return "\n".join(lines)

class EvolutionAnalyzer:
    """Outils d’analyse des tendances de personnalité"""

    @staticmethod
    def analyze_trends(evolution_history: List[PersonalityEvolution]) -> Dict[str, Any]:
        if not evolution_history:
            return {}

        trends = defaultdict(list)
        for evo in evolution_history:
            if evo.change_type.startswith("trait_"):
                trait = evo.change_type[6:]
                trends[trait].append({"value": evo.new_value, "timestamp": evo.timestamp.isoformat()})

        analysis: Dict[str, Any] = {}
        for trait, changes in trends.items():
            if len(changes) >= 2:
                values = [float(c["value"]) for c in changes]
                analysis[trait] = {
                    "direction": "increasing" if values[-1] > values[0] else "decreasing",
                    "volatility": float(np.std(values)),
                    "total_change": float(values[-1] - values[0]),
                }
        return analysis