# src/middleware/advanced_rate_limiter.py
"""Module implémentant un limiteur de débit (rate limiter) avancé.

Ce limiteur de débit permet de contrôler le nombre de requêtes qu'un utilisateur
ou une entité peut effectuer dans une période donnée. Il supporte différentes
catégories de limites (ex: par défaut, analyse, génération) et est conçu pour
être utilisé de manière asynchrone.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class AdvancedRateLimiter:
    """Implémente un limiteur de débit configurable avec différentes catégories de limites."""

    def __init__(self):
        """Initialise le limiteur de débit avec des limites prédéfinies."

        `limits` est un dictionnaire où chaque clé est une catégorie (ex: "default", "analysis").
        Chaque catégorie contient le nombre maximal de requêtes et la fenêtre de temps en secondes.
        `requests` stocke les horodatages des requêtes pour chaque clé (utilisateur/IP).
        """
        self.limits: Dict[str, Dict[str, int]] = {
            "default": {"requests": 100, "window": 3600}, # 100 requêtes par heure.
            "analysis": {"requests": 20, "window": 3600}, # 20 requêtes d'analyse par heure.
            "generation": {"requests": 50, "window": 3600}, # 50 requêtes de génération par heure.
        }
        self.requests: Dict[str, List[datetime]] = defaultdict(list)

    async def check_limit(self, key: str, category: str = "default") -> bool:
        """Vérifie si une requête est autorisée selon les limites de débit."

        Args:
            key: La clé unique pour laquelle la limite est vérifiée (ex: adresse IP, ID utilisateur).
            category: La catégorie de limite à appliquer (ex: "default", "analysis").

        Returns:
            True si la requête est autorisée, False si la limite est dépassée.
        """
        now = datetime.now()
        limit_config = self.limits.get(category, self.limits["default"])

        # Nettoie les anciennes requêtes qui sont en dehors de la fenêtre de temps.
        cutoff = now - timedelta(seconds=limit_config["window"])
        self.requests[f"{category}:{key}"] = [
            req for req in self.requests[f"{category}:{key}"]
            if req > cutoff
        ]

        # Vérifie si le nombre de requêtes actuelles dépasse la limite.
        if len(self.requests[f"{category}:{key}"]) >= limit_config["requests"]:
            logger.warning(f"Limite de débit dépassée pour la clé '{key}' dans la catégorie '{category}'.")
            return False

        # Enregistre la nouvelle requête.
        self.requests[f"{category}:{key}"].append(now)
        return True


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def demo():
        limiter = AdvancedRateLimiter()

        print("\n--- Démonstration de la limite par défaut (100/heure) ---")
        user_ip = "192.168.1.100"
        for i in range(5):
            allowed = await limiter.check_limit(user_ip)
            print(f"Requête {i+1} par {user_ip} : {'Autorisée' if allowed else 'Bloquée'}")
            await asyncio.sleep(0.01) # Petite pause.

        print("\n--- Démonstration de la limite 'analysis' (20/heure) ---")
        user_id = "user_alice"
        for i in range(25):
            allowed = await limiter.check_limit(user_id, category="analysis")
            print(f"Requête d'analyse {i+1} par {user_id} : {'Autorisée' if allowed else 'Bloquée'}")
            if not allowed:
                break
            await asyncio.sleep(0.01)

        print("\n--- Démonstration de la réinitialisation après fenêtre de temps ---")
        # Simule le passage du temps pour réinitialiser la limite.
        limiter.limits["short_test"] = {"requests": 2, "window": 1}
        test_key = "short_lived_user"

        print("Requête 1 (short_test) :", "Autorisée" if await limiter.check_limit(test_key, "short_test") else "Bloquée")
        print("Requête 2 (short_test) :", "Autorisée" if await limiter.check_limit(test_key, "short_test") else "Bloquée")
        print("Requête 3 (short_test) :", "Autorisée" if await limiter.check_limit(test_key, "short_test") else "Bloquée")

        print("Attente de 1.1 seconde pour la réinitialisation...")
        await asyncio.sleep(1.1)

        print("Requête 4 (short_test) après réinitialisation :", "Autorisée" if await limiter.check_limit(test_key, "short_test") else "Bloquée")

        print("Démonstration du limiteur de débit terminée.")

    asyncio.run(demo())