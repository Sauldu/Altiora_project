from typing import List
import redis.asyncio as redis

# src/cache/redis_cluster.py
class RedisClusterClient:
    """Client pour interagir avec un cluster Redis en mode asynchrone.

    Ce client est conçu pour fournir une haute disponibilité et une scalabilité
    pour les opérations de cache en utilisant les fonctionnalités de cluster de Redis.
    """
    def __init__(self, nodes: List[str]):
        """Initialise le client de cluster Redis.

        Args:
            nodes: Une liste de chaînes de caractères représentant les nœuds de démarrage
                   du cluster Redis (ex: ["redis://host1:port1", "redis://host2:port2"]).
        """
        self.cluster = redis.cluster.RedisCluster(
            startup_nodes=nodes,
            skip_full_coverage_check=True # Peut être utile pour les environnements de développement.
        )

    async def get(self, key: str):
        """Récupère la valeur associée à une clé dans le cluster Redis."

        Args:
            key: La clé à récupérer.

        Returns:
            La valeur associée à la clé, ou None si la clé n'existe pas.
        """
        return await self.cluster.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        """Définit la valeur d'une clé dans le cluster Redis."

        Args:
            key: La clé à définir.
            value: La valeur à associer à la clé.
            ex: La durée d'expiration de la clé en secondes (TTL). Si None, la clé n'expire pas.
        """
        await self.cluster.set(key, value, ex=ex)


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def demo():
        print("\n--- Démonstration du RedisClusterClient (nécessite un cluster Redis en cours d'exécution) ---")
        # Remplacez par les adresses de vos nœuds de cluster Redis.
        # Pour une démonstration locale, vous pouvez simuler un cluster avec Docker Compose.
        nodes = ["redis://localhost:7000", "redis://localhost:7001"]
        
        try:
            client = RedisClusterClient(nodes)
            
            # Test de connexion au cluster.
            await client.set("test_key", "Hello Redis Cluster!")
            value = await client.get("test_key")
            print(f"Valeur récupérée : {value.decode() if value else 'None'}")

            # Test avec expiration.
            await client.set("temp_key", "Ephemeral data", ex=5)
            print("Clé 'temp_key' définie avec expiration de 5 secondes.")
            await asyncio.sleep(6)
            expired_value = await client.get("temp_key")
            print(f"Valeur de 'temp_key' après expiration : {expired_value.decode() if expired_value else 'None'}")

        except Exception as e:
            logging.error(f"Erreur lors de la démonstration du cluster Redis : {e}")
            print("Assurez-vous que votre cluster Redis est correctement configuré et accessible.")

    asyncio.run(demo())