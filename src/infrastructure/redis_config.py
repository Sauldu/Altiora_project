# src/infrastructure/redis_config.py
"""Module de gestion centralisée du client Redis asynchrone.

Ce module fournit une classe `RedisManager` pour gérer l'initialisation
et la fermeture du client Redis. Il implémente le pattern Singleton pour
s'assurer qu'une seule instance du client Redis est utilisée dans toute
l'application, optimisant ainsi les connexions et les ressources.
"""

import redis.asyncio as redis
import logging
from typing import Optional

from configs.config_module import get_settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Gère l'instance unique du client Redis pour l'application."""

    def __init__(self):
        """Initialise le gestionnaire Redis.

        Charge les paramètres de connexion Redis via `get_settings()`.
        Le client Redis n'est pas créé immédiatement, mais lors du premier appel à `get_client()`.
        """
        self.settings = get_settings().redis # Accède directement à la sous-section Redis de la config.
        self._client: Optional[redis.Redis] = None

    async def get_client(self) -> redis.Redis:
        """Récupère ou crée l'instance du client Redis.

        Si le client n'est pas encore initialisé, il est créé en utilisant les
        paramètres de configuration. Cette méthode est idempotente.

        Returns:
            L'instance du client `redis.asyncio.Redis`.
        """
        if self._client is None:
            logger.info(f"Initialisation du client Redis pour {self.settings.url}...")
            try:
                self._client = await redis.from_url(
                    self.settings.url,
                    password=self.settings.password,
                    decode_responses=True, # Décode automatiquement les réponses en UTF-8.
                    max_connections=self.settings.max_connections # Utilise le paramètre de max_connections.
                )
                await self._client.ping() # Vérifie la connexion.
                logger.info("✅ Client Redis initialisé et connecté.")
            except Exception as e:
                logger.critical(f"❌ Échec de l'initialisation du client Redis : {e}")
                raise # Relève l'exception car Redis est une dépendance critique.
        return self._client

    async def close(self):
        """Ferme la connexion Redis si elle est ouverte.

        Cette méthode doit être appelée lors de l'arrêt de l'application pour
        libérer les ressources de connexion.
        """
        if self._client:
            logger.info("Fermeture de la connexion Redis...")
            await self._client.close()
            self._client = None
            logger.info("✅ Connexion Redis fermée.")


# Instance singleton du gestionnaire Redis.
_redis_manager = RedisManager()


async def get_redis_client() -> redis.Redis:
    """Fonction utilitaire pour récupérer l'instance singleton du client Redis.

    C'est la méthode préférée pour obtenir le client Redis dans toute l'application.

    Returns:
        L'instance du client `redis.asyncio.Redis`.
    """
    return await _redis_manager.get_client()


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import os
    from configs.config_module import get_settings # Pour s'assurer que les settings sont chargés.

    async def demo():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Assurez-vous que les settings sont chargés (simule le démarrage de l'app).
        # Vous pouvez définir des variables d'environnement pour tester différents scénarios.
        # os.environ["REDIS_HOST"] = "localhost"
        # os.environ["REDIS_PORT"] = "6379"
        # os.environ["REDIS_PASSWORD"] = "mysecretpassword"
        # os.environ["REDIS_MAX_CONNECTIONS"] = "20"
        _ = get_settings() # Charge les settings.

        print("\n--- Démonstration de get_redis_client() ---")
        try:
            client1 = await get_redis_client()
            print(f"Client 1 : {client1}")
            response = await client1.set("mykey", "myvalue")
            print(f"SET mykey: {response}")
            value = await client1.get("mykey")
            print(f"GET mykey: {value}")

            client2 = await get_redis_client()
            print(f"Client 2 : {client2}")
            assert client1 is client2, "Les clients devraient être la même instance (singleton)."

        except Exception as e:
            logging.error(f"Erreur lors de la démonstration Redis : {e}")
            print("Assurez-vous qu'un serveur Redis est en cours d'exécution sur localhost:6379.")
        finally:
            # Ferme la connexion Redis à la fin de la démonstration.
            await _redis_manager.close()

    asyncio.run(demo())
