# src/modules/psychodesign/altiora_core.py
"""Noyau de personnalité et d'apprentissage supervisé pour l'IA Altiora.

Ce module gère les traits de personnalité de l'IA, son évolution via le
feedback utilisateur et l'apprentissage supervisé. Il intègre des mécanismes
de validation administrative pour assurer une évolution contrôlée et sécurisée.
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
from src.modules.psychodesign.personality_quiz import PersonalityProfile

logger = logging.getLogger(__name__)


@dataclass
class PersonalityEvolution:
    """Enregistrement d'un changement dans les traits de personnalité de l'IA."""
    timestamp: datetime
    change_type: str # Type de changement (ex: 'trait_formalite', 'preference_update').
    old_value: float # Ancienne valeur du trait ou de la préférence.
    new_value: float # Nouvelle valeur du trait ou de la préférence.
    reason: str      # Raison du changement (ex: 'feedback utilisateur', 'ajustement automatique').
    source: str      # Source du changement (ex: 'auto', 'user_feedback', 'admin_override').
    approved: bool = False # Indique si le changement a été approuvé par un administrateur.
    admin_review: Optional[str] = None # Commentaires de l'administrateur.


@dataclass
class LearningProposal:
    """Représente une proposition de modification de la personnalité issue de l'apprentissage supervisé."""
    proposal_id: str
    user_id: str
    suggested_changes: Dict[str, Any] # Changements proposés (ex: {"formalite": 0.7}).
    confidence_score: float # Score de confiance de la proposition (entre 0 et 1).
    evidence: List[Dict[str, Any]] # Preuves ou données brutes ayant mené à la proposition.
    timestamp: datetime
    status: str = "pending" # Statut de la proposition ('pending', 'approved', 'rejected').
    admin_decision: Optional[str] = None # Décision de l'administrateur.


class AltioraCore:
    """Moteur de personnalité de l'IA avec capacités d'apprentissage supervisé."""

    def __init__(self, user_id: str, admin_system: AdminControlSystem):
        """Initialise le noyau Altiora."

        Args:
            user_id: L'identifiant de l'utilisateur associé à cette instance du noyau.
            admin_system: Une instance de `AdminControlSystem` pour la gestion des commandes administratives.
        """
        self.user_id = user_id
        self.admin_system = admin_system
        self.ethical_safeguards = EthicalSafeguards() # Système de garde-fous éthiques.

        self.core_path = Path("altiora_core") # Répertoire pour la persistance des données du noyau.
        self.core_path.mkdir(exist_ok=True)

        self.personality = self._load_default_personality()
        self.evolution_history: List[PersonalityEvolution] = []
        self.learning_proposals: List[LearningProposal] = []

        self.supervised_mode = False # Mode d'apprentissage supervisé (True/False).
        self.learning_mode = "conservative" # Stratégie d'apprentissage ('conservative', 'adaptive').
        self.logger = self._setup_logging()

    # ------------------------------------------------------------------
    # Initialisation et Persistance
    # ------------------------------------------------------------------

    def _setup_logging(self) -> logging.Logger:
        """Configure un logger spécifique pour cette instance du noyau Altiora."""
        logger = logging.getLogger(f"altiora_core_{self.user_id}")
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(self.core_path / f"{self.user_id}.log")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def _load_default_personality(self) -> PersonalityProfile:
        """Charge le profil de personnalité de l'utilisateur depuis le disque, ou crée un profil par défaut."

        Returns:
            L'objet `PersonalityProfile` chargé ou par défaut.
        """
        profile_file = self.core_path / f"{self.user_id}_profile.json"
        if profile_file.exists():
            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return PersonalityProfile(**data)
            except (IOError, OSError, json.JSONDecodeError) as e:
                self.logger.error(f"Erreur lors du chargement du profil pour {self.user_id}: {e}")

        # Retourne un profil par défaut si aucun n'est trouvé ou si le chargement échoue.
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
    # API Publique – Interaction et Apprentissage
    # ------------------------------------------------------------------

    async def process_learning_feedback(self, feedback: Dict[str, Any]) -> Optional[LearningProposal]:
        """Traite un feedback utilisateur et génère une proposition d'apprentissage."

        Args:
            feedback: Un dictionnaire contenant le feedback de l'utilisateur.

        Returns:
            Une `LearningProposal` si une proposition est générée, sinon None.
        """
        feedback_type = feedback.get("type")
        if feedback_type == "correction":
            return await self._handle_correction_feedback(feedback)
        if feedback_type == "adjustment":
            return await self._handle_adjustment_feedback(feedback)
        if feedback_type == "explicit_preference":
            return await self._handle_preference_feedback(feedback) # Méthode à implémenter.
        return None

    async def handle_user_interaction(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse une interaction utilisateur, applique les garde-fous éthiques et génère une réponse personnalisée."

        Args:
            interaction: Un dictionnaire décrivant l'interaction de l'utilisateur.

        Returns:
            Un dictionnaire contenant la réponse de l'IA et potentiellement des informations sur les propositions d'apprentissage.
        """
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
    # Gestion des Propositions d'Apprentissage
    # ------------------------------------------------------------------

    async def _handle_correction_feedback(self, feedback: Dict[str, Any]) -> Optional[LearningProposal]:
        """Traite le feedback de correction et génère une proposition d'apprentissage."""
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
        """Traite le feedback d'ajustement et génère une proposition d'apprentissage."""
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
        new_value = max(0.0, min(1.0, self.personality.traits[trait] + delta)) # Assure que la valeur reste entre 0 et 1.

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

    async def _handle_preference_feedback(self, feedback: Dict[str, Any]) -> Optional[LearningProposal]:
        """Traite le feedback de préférence explicite et génère une proposition d'apprentissage."""
        # TODO: Implémenter la logique pour analyser le feedback de préférence.
        self.logger.warning(f"Feedback de préférence explicite non implémenté : {feedback}")
        return None

    # ------------------------------------------------------------------
    # Fonctions internes
    # ------------------------------------------------------------------

    def _analyze_correction_impact(self, original: Optional[str], corrected: Optional[str]) -> Dict[str, float]:
        """Analyse l'impact d'une correction sur les traits de personnalité (ex: verbosité, formalité)."""
        changes: Dict[str, float] = {}
        if not original or not corrected:
            return changes

        # Exemple: Ajustement de la verbosité si la correction est significativement plus courte.
        if len(corrected) < len(original) * 0.8:
            changes["verbosite"] = max(0.0, self.personality.traits["verbosite"] - 0.1)

        # Exemple: Ajustement de la formalité basé sur la présence de certains indicateurs.
        formal_indicators = ["vous", "monsieur", "madame"]
        orig_formal = any(w in str(original).lower() for w in formal_indicators)
        corr_formal = any(w in str(corrected).lower() for w in formal_indicators)
        if orig_formal != corr_formal:
            delta = 0.1 if corr_formal else -0.1
            changes["formalite"] = max(0.0, min(1.0, self.personality.traits["formalite"] + delta))
        return changes

    async def _submit_for_admin_review(self, proposal: LearningProposal) -> None:
        """Soumet une proposition d'apprentissage à l'administrateur pour examen et approbation."""
        command = AdminCommand(
            command_id=proposal.proposal_id,
            timestamp=datetime.now(),
            action="review_learning_proposal",
            target_user=self.user_id,
            parameters={
                "proposal": asdict(proposal),
                "user_id": self.user_id # Ajout de l'user_id pour le contexte admin.
            },
        )
        await self.admin_system.execute_admin_command(command)
        self.logger.info("Proposition d'apprentissage soumise pour examen : %s", proposal.proposal_id)

    async def _generate_response(self) -> Dict[str, Any]:
        """Génère une réponse de l'IA basée sur la personnalité actuelle (stub)."""
        # TODO: Intégrer un modèle de génération de texte qui utilise les traits de personnalité.
        return {
            "status": "success",
            "response": "Réponse générée selon la personnalité actuelle (implémentation à venir).",
            "personality_snapshot": self.personality.traits,
        }

    async def apply_approved_changes(self, proposal_id: str) -> bool:
        """Applique les changements de personnalité validés par un administrateur."

        Args:
            proposal_id: L'ID de la proposition d'apprentissage approuvée.

        Returns:
            True si les changements ont été appliqués, False sinon.
        """
        proposal = next((p for p in self.learning_proposals if p.proposal_id == proposal_id), None)
        if not proposal or proposal.status != "approved":
            self.logger.warning(f"Proposition {proposal_id} non trouvée ou non approuvée. Changements non appliqués.")
            return False

        for trait, new_value in proposal.suggested_changes.items():
            old_value = self.personality.traits.get(trait, 0.5) # Récupère l'ancienne valeur.
            evolution = PersonalityEvolution(
                timestamp=datetime.now(),
                change_type=f"trait_{trait}",
                old_value=old_value,
                new_value=float(new_value),
                reason=f"Approbation de la proposition d'apprentissage {proposal_id}",
                source="learning",
                approved=True,
            )
            self.evolution_history.append(evolution)
            self.personality.traits[trait] = float(new_value) # Applique le nouveau trait.
            self.logger.info(f"Trait '{trait}' mis à jour de {old_value:.2f} à {new_value:.2f}.")

        await self._save_state()
        self.logger.info("Changements de personnalité appliqués : %s", proposal.suggested_changes)
        return True

    async def _save_state(self) -> None:
        """Sauvegarde l'état complet du noyau Altiora (personnalité, historique, propositions)."""
        try:
            # Sauvegarde le profil de personnalité.
            with open(self.core_path / f"{self.user_id}_profile.json", "w", encoding='utf-8') as f:
                json.dump(asdict(self.personality), f, indent=2, default=str)
            # Sauvegarde l'historique d'évolution.
            with open(self.core_path / f"{self.user_id}_evolution.json", "w", encoding='utf-8') as f:
                json.dump([asdict(e) for e in self.evolution_history], f, indent=2, default=str)
            # Sauvegarde les propositions d'apprentissage.
            with open(self.core_path / f"{self.user_id}_proposals.json", "w", encoding='utf-8') as f:
                json.dump([asdict(p) for p in self.learning_proposals], f, indent=2, default=str)
            self.logger.info(f"État du noyau Altiora sauvegardé pour l'utilisateur {self.user_id}.")
        except (IOError, OSError) as e:
            self.logger.error(f"Erreur lors de la sauvegarde de l'état pour {self.user_id}: {e}")

    # ------------------------------------------------------------------
    # Accès en lecture (pour le reporting ou le débogage)
    # ------------------------------------------------------------------

    def get_personality_summary(self) -> Dict[str, Any]:
        """Retourne un résumé des traits de personnalité actuels et des statistiques d'apprentissage."""
        return {
            "user_id": self.user_id,
            "current_traits": self.personality.traits,
            "evolution_count": len(self.evolution_history),
            "pending_proposals": len([p for p in self.learning_proposals if p.status == "pending"]),
            "last_change": self.evolution_history[-1].timestamp.isoformat() if self.evolution_history else None,
            "supervised_mode": self.supervised_mode,
            "learning_mode": self.learning_mode,
        }

    def get_evolution_report(self) -> str:
        """Génère un rapport textuel de l'évolution de la personnalité."""
        lines = [f"📈 **Rapport d'Évolution - {self.user_id}**", "", "**Traits actuels :**"]
        lines.extend(f"• {k} : {v:.1%}" for k, v in self.personality.traits.items())
        lines += [
            "",
            f"**Historique :** {len(self.evolution_history)} changements",
            f"**Propositions en attente :** {len([p for p in self.learning_proposals if p.status == 'pending'])} ",
            f"**Mode apprentissage :** {self.learning_mode}",
        ]
        return "\n".join(lines)


class EvolutionAnalyzer:
    """Outils d'analyse des tendances de personnalité à partir de l'historique d'évolution."""

    @staticmethod
    def analyze_trends(evolution_history: List[PersonalityEvolution]) -> Dict[str, Any]:
        """Analyse les tendances d'évolution des traits de personnalité."

        Args:
            evolution_history: La liste des objets `PersonalityEvolution`.

        Returns:
            Un dictionnaire contenant des analyses de tendances pour chaque trait.
        """
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


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Classe factice pour AdminControlSystem pour la démonstration.
    class MockAdminControlSystem:
        async def execute_admin_command(self, command: AdminCommand):
            logging.info(f"[MockAdmin] Commande reçue : {command.action} pour {command.target_user}")
            if command.action == "review_learning_proposal":
                # Simule l'approbation automatique pour la démo.
                proposal_id = command.command_id
                for prop in altiora_core_instance.learning_proposals:
                    if prop.proposal_id == proposal_id:
                        prop.status = "approved"
                        prop.admin_decision = "Approuvé automatiquement pour la démo."
                        logging.info(f"[MockAdmin] Proposition {proposal_id} approuvée.")
                        break

    async def demo():
        user_id = "demo_user_1"
        mock_admin = MockAdminControlSystem()
        global altiora_core_instance # Rendre l'instance accessible au mock_admin.
        altiora_core_instance = AltioraCore(user_id, mock_admin)

        print("\n--- Profil de personnalité initial ---")
        print(altiora_core_instance.get_personality_summary())

        print("\n--- Simulation d'interaction utilisateur et feedback ---")
        # Simule un feedback de correction.
        feedback_correction = {
            "type": "correction",
            "original": "Le rapport est trop long et formel.",
            "corrected": "Rapport concis."
        }
        await altiora_core_instance.handle_user_interaction(feedback_correction)

        # Simule un feedback d'ajustement.
        feedback_adjustment = {
            "type": "adjustment",
            "adjustment_type": "shorter"
        }
        await altiora_core_instance.handle_user_interaction(feedback_adjustment)

        print("\n--- Propositions d'apprentissage en attente ---")
        for prop in altiora_core_instance.learning_proposals:
            print(f"Proposition ID: {prop.proposal_id}, Statut: {prop.status}, Changements: {prop.suggested_changes}")

        # Simule l'approbation des propositions par l'admin.
        print("\n--- Application des changements approuvés (simulée par l'admin) ---")
        for prop in altiora_core_instance.learning_proposals:
            if prop.status == "pending":
                # L'admin mock va approuver la proposition.
                await mock_admin.execute_admin_command(AdminCommand(
                    command_id=prop.proposal_id,
                    timestamp=datetime.now(),
                    action="review_learning_proposal",
                    target_user=user_id,
                    parameters={'proposal': asdict(prop)}
                ))
                await altiora_core_instance.apply_approved_changes(prop.proposal_id)

        print("\n--- Profil de personnalité après apprentissage ---")
        print(altiora_core_instance.get_personality_summary())

        print("\n--- Rapport d'évolution ---")
        print(altiora_core_instance.get_evolution_report())

        print("\n--- Analyse des tendances ---")
        trends = EvolutionAnalyzer.analyze_trends(altiora_core_instance.evolution_history)
        print(f"Tendances : {trends}")

        print("Démonstration de AltioraCore terminée.")

    asyncio.run(demo())