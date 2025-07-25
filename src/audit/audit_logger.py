# src/audit/audit_logger.py
"""Module pour la journalisation des actions d'audit dans l'application.

Ce module fournit une classe `AuditLogger` pour enregistrer les actions
significatives des utilisateurs et du système. Les entrées d'audit sont
horodatées, contiennent des détails sur l'action, l'utilisateur, l'adresse IP
et l'ID de session, et sont stockées dans Redis avec une durée de vie (TTL)
pour la conformité RGPD.
"""

import datetime
import json
import logging
from typing import Dict, Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)


def get_client_ip() -> str:
    """Fonction factice pour récupérer l'adresse IP du client.

    Dans une application réelle, cette fonction récupérerait l'IP depuis la requête HTTP.
    """
    # TODO: Implémenter la récupération réelle de l'adresse IP du client.
    return "unknown"


def get_session_id() -> str:
    """Fonction factice pour récupérer l'ID de session.

    Dans une application réelle, cette fonction récupérerait l'ID de session depuis le contexte.
    """
    # TODO: Implémenter la récupération réelle de l'ID de session.
    return "unknown"


class AuditLogger:
    """Enregistre les événements d'audit dans Redis."""

    def __init__(self, redis_client: redis.Redis):
        """Initialise le logger d'audit avec un client Redis."

        Args:
            redis_client: Une instance de `redis.asyncio.Redis` connectée.
        """
        self.redis = redis_client

    async def log_action(self, action: str, user_id: str, details: Dict[str, Any]):
        """Enregistre une action d'audit.

        Les entrées d'audit sont stockées dans Redis avec un TTL de 90 jours
        (7776000 secondes) pour la conformité RGPD.

        Args:
            action: Le nom de l'action effectuée (ex: 'login', 'sfd_upload').
            user_id: L'identifiant de l'utilisateur qui a effectué l'action.
            details: Un dictionnaire contenant des détails supplémentaires sur l'action.
        """
        audit_entry = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "details": details,
            "ip_address": get_client_ip(),
            "session_id": get_session_id()
        }

        # Génère une clé unique pour l'entrée d'audit.
        key = f"audit:{user_id}:{datetime.datetime.utcnow().timestamp()}"
        try:
            # Stocke l'entrée d'audit dans Redis avec un TTL.
            await self.redis.setex(key, 7776000, json.dumps(audit_entry, ensure_ascii=False))
            logger.info(f"Action d'audit enregistrée : {action} par {user_id}")
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de l'action d'audit dans Redis : {e}")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        
        # Assurez-vous qu'un serveur Redis est en cours d'exécution.
        try:
            redis_client = redis.Redis(host='localhost', port=6379, db=0)
            await redis_client.ping()
            logger.info("Connecté à Redis pour la démonstration.")
        except Exception as e:
            logger.error(f"Impossible de se connecter à Redis : {e}. La démonstration ne peut pas continuer.")
            return

        logger = AuditLogger(redis_client)

        print("\n--- Enregistrement d'actions d'audit ---")
        await logger.log_action("login", "user_alice", {"method": "password", "success": True})
        await logger.log_action("sfd_upload", "user_bob", {"file_name": "spec_v1.pdf", "size_kb": 1024})
        await logger.log_action("test_generation", "user_charlie", {"model": "starcoder2", "scenarios_count": 5})

        print("\n--- Vérification des entrées d'audit (peut prendre un moment) ---")
        # Pour une vérification réelle, vous devriez interroger Redis.
        # Exemple (simplifié, ne récupère pas toutes les clés): 
        # keys = await redis_client.keys("audit:*")
        # for key in keys:
        #     entry = await redis_client.get(key)
        #     print(json.loads(entry))
        print("Vérifiez votre instance Redis pour les entrées d'audit.")

        await redis_client.close()
        print("Démonstration terminée.")

    import asyncio
    asyncio.run(demo())