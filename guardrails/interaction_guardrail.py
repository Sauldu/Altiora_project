# guardrails/interaction_guardrail.py
"""Gardien des interactions en temps réel pour Altiora.

Ce module agit comme un portail de sécurité pour toutes les entrées utilisateur.
Il applique un ensemble de politiques de sécurité (confidentialité, toxicité, etc.)
à chaque message ou contenu soumis par un utilisateur, et retourne un verdict
instantané sur sa conformité.
"""

import asyncio
from typing import Dict, Any
from .policy_enforcer import PolicyEnforcer
import logging

logger = logging.getLogger(__name__)


class InteractionGuardrail:
    """Façade de sécurité à utiliser à chaque point d'entrée faisant face à l'utilisateur.

    Cette classe doit être instanciée et sa méthode `check` doit être appelée
    chaque fois que l'application reçoit des données d'un utilisateur, par exemple via :
    - un message de chat ;
    - un téléversement de fichier ;
    - une transcription vocale ;
    - une spécification fonctionnelle soumise pour analyse.
    """

    def __init__(self):
        """Initialise le gardien avec une instance du `PolicyEnforcer`."""
        self.enforcer = PolicyEnforcer()

    async def check(
        self,
        user_id: str,
        raw_text: str,
        *,
        source: str = "chat",
        extra_meta: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Analyse un texte brut et retourne un verdict de sécurité.

        Args:
            user_id: L'identifiant de l'utilisateur qui soumet le texte.
            raw_text: Le contenu textuel à vérifier.
            source: La source de l'interaction (ex: 'chat', 'sfd_upload').
            extra_meta: Un dictionnaire de métadonnées supplémentaires à inclure dans l'audit.

        Returns:
            Un dictionnaire contenant le verdict :
            {
                "allowed": bool,      # True si le contenu est autorisé, False sinon.
                "masked_text": str, # Le texte avec les informations sensibles masquées.
                "violations": list[str], # La liste des politiques violées.
                "audit_id": str,    # Une référence rapide à l'enregistrement d'audit.
            }
        """
        # Le `PolicyEnforcer` est le moteur qui applique toutes les politiques configurées.
        verdict = await self.enforcer.enforce(
            user_id=user_id,
            context=raw_text,
            workflow=source,
            extra_meta=extra_meta or {},
        )
        return {
            "allowed": verdict["allowed"],
            "masked_text": verdict["masked_context"],
            "violations": verdict["violations"],
            "audit_id": verdict["audit"]["timestamp"],  # Référence rapide
        }

    # ------------------------------------------------------------------
    # Wrapper synchrone pour les cas d'utilisation non-asynchrones
    # ------------------------------------------------------------------
    def check_sync(self, user_id: str, raw_text: str, **kw) -> Dict[str, Any]:
        """Wrapper synchrone pour la méthode `check`."""
        return asyncio.run(self.check(user_id, raw_text, **kw))


# ------------------------------------------------------------------
# Test rapide en ligne de commande pour la démonstration
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        gate = InteractionGuardrail()
        samples = [
            ("alice", "Salut, ça va ?"),
            ("bob", "Mon email est bob@mail.fr"),
            ("mallory", "T’es vraiment un naze"),
        ]
        for uid, txt in samples:
            res = await gate.check(uid, txt)
            logger.info(f"{uid}: {txt}")
            logger.info(f"→ allowed: {res['allowed']}")
            logger.info(f"→ masked: {res['masked_text']}")
            print("-" * 40)

    asyncio.run(demo())
