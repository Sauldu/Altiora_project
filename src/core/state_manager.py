# src/core/state_manager.py
"""StateManager – gestionnaire d'état centralisé basé sur Redis.

Ce module fournit une interface pour gérer l'état de l'application de manière
persistante et distribuée en utilisant Redis. Il supporte le suivi de la progression
des pipelines, l'état des sessions utilisateur et un cache à court terme.
En cas d'indisponibilité de Redis, il bascule automatiquement sur un cache en mémoire.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class StateManager:
    """Gestionnaire d'état de l'application avec persistance Redis et fallback en mémoire."""

    def __init__(self, redis_url: str, *, ttl: int = 3600) -> None:
        """Initialise le gestionnaire d'état.

        Args:
            redis_url: L'URL de connexion au serveur Redis.
            ttl: La durée de vie par défaut (en secondes) pour les entrées de cache.
        """
        self._redis_url: str = redis_url
        self._ttl: int = ttl
        self._redis: Optional[redis.Redis] = None
        self._memory_cache: Dict[str, Any] = {}  # Cache de fallback en mémoire.

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Tente de se connecter à Redis. En cas d'échec, utilise le cache en mémoire."""
        try:
            self._redis = await redis.from_url(
                self._redis_url, decode_responses=True
            )
            await self._redis.ping()  # Vérifie la connexion.
            logger.info("✅ StateManager : Connecté à Redis.")
        except Exception as exc:
            self._redis = None
            logger.warning(f"⚠️ StateManager : Redis non disponible – utilisation du fallback en mémoire : {exc}")

    async def close(self) -> None:
        """Ferme la connexion Redis si elle est ouverte."""
        if self._redis:
            await self._redis.aclose()
            logger.info("✅ StateManager : Connexion Redis fermée.")

    # ------------------------------------------------------------------
    # Suivi de la progression du pipeline
    # ------------------------------------------------------------------

    async def set_pipeline_progress(
            self, session_id: str, step: str, progress: float
    ) -> None:
        """Enregistre la progression d'une étape spécifique d'un pipeline.

        Args:
            session_id: L'identifiant unique de la session du pipeline.
            step: Le nom de l'étape du pipeline (ex: 'analyse_sfd').
            progress: La progression de l'étape (généralement entre 0.0 et 1.0).
        """
        key = f"pipeline:{session_id}:{step}"
        value = {"progress": progress, "updated": datetime.utcnow().isoformat()}
        await self._set(key, value)

    async def get_pipeline_progress(self, session_id: str) -> Dict[str, Any]:
        """Récupère la progression de toutes les étapes d'un pipeline donné.

        Args:
            session_id: L'identifiant unique de la session du pipeline.

        Returns:
            Un dictionnaire où les clés sont les noms des étapes et les valeurs
            sont leurs objets de progression.
        """
        pattern = f"pipeline:{session_id}:*"
        if self._redis:
            # Utilise `keys` pour récupérer toutes les clés correspondant au pattern.
            keys = await self._redis.keys(pattern)
            # Récupère les valeurs pour toutes les clés en parallèle.
            data = await asyncio.gather(*[self._get(k) for k in keys])
            # Construit le dictionnaire de résultats.
            return {k.split(":", 2)[-1]: v for k, v in zip(keys, data) if v}
        
        # Fallback en mémoire : filtre les éléments du cache qui correspondent au pattern.
        return {
            k.split(":", 2)[-1]: v["data"]
            for k, v in self._memory_cache.items()
            if k.startswith(pattern) and v.get("expires", datetime.min) > datetime.utcnow()
        }

    # ------------------------------------------------------------------
    # Gestion de l'état de session
    # ------------------------------------------------------------------

    async def set_session(self, session_id: str, data: Dict[str, Any]) -> None:
        """Enregistre l'état complet d'une session utilisateur.

        Args:
            session_id: L'identifiant unique de la session.
            data: Le dictionnaire de données représentant l'état de la session.
        """
        key = f"session:{session_id}"
        await self._set(key, data)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Récupère l'état d'une session utilisateur.

        Args:
            session_id: L'identifiant unique de la session.

        Returns:
            Le dictionnaire de données de la session, ou None si non trouvé.
        """
        key = f"session:{session_id}"
        return await self._get(key)

    # ------------------------------------------------------------------
    # Assistants génériques (internes)
    # ------------------------------------------------------------------

    async def _set(self, key: str, value: Any) -> None:
        """Définit une clé-valeur dans Redis ou dans le cache en mémoire."""
        if self._redis:
            await self._redis.setex(key, self._ttl, json.dumps(value))
        else:
            self._memory_cache[key] = {
                "data": value,
                "expires": datetime.utcnow() + timedelta(seconds=self._ttl),
            }

    async def _get(self, key: str) -> Optional[Dict[str, Any]]:
        """Récupère une valeur par sa clé depuis Redis ou le cache en mémoire."""
        if self._redis:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None

        # Fallback en mémoire : vérifie l'existence et l'expiration.
        item = self._memory_cache.get(key)
        if item and item.get("expires", datetime.min) > datetime.utcnow():
            return item["data"]
        # Supprime l'élément expiré du cache en mémoire.
        self._memory_cache.pop(key, None)
        return None

    # ------------------------------------------------------------------
    # Vérification de l'état de santé
    # ------------------------------------------------------------------

    async def health(self) -> bool:
        """Vérifie l'état de santé de la connexion Redis.

        Returns:
            True si Redis est accessible, False sinon.
        """
        if not self._redis:
            return False
        try:
            return await self._redis.ping()
        except Exception:
            return False


# ------------------------------------------------------------------
# Assistant Singleton
# ------------------------------------------------------------------

_state_manager: Optional[StateManager] = None


async def get_state_manager(redis_url: str = "redis://localhost:6379") -> StateManager:
    """Fournit une instance singleton du StateManager.

    Args:
        redis_url: L'URL de connexion à Redis.

    Returns:
        L'instance unique du StateManager.
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager(redis_url)
        await _state_manager.initialize()
    return _state_manager


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Démonstration avec Redis (assurez-vous que Redis est lancé)
        print("\n--- Démonstration avec Redis ---")
        sm_redis = await get_state_manager("redis://localhost:6379")
        session_id_redis = "test_session_redis_123"

        await sm_redis.set_session(session_id_redis, {"user": "Alice", "status": "active"})
        await sm_redis.set_pipeline_progress(session_id_redis, "step1", 0.5)
        await sm_redis.set_pipeline_progress(session_id_redis, "step2", 0.2)

        session_data = await sm_redis.get_session(session_id_redis)
        print(f"Données de session (Redis) : {session_data}")

        progress_data = await sm_redis.get_pipeline_progress(session_id_redis)
        print(f"Progression du pipeline (Redis) : {progress_data}")

        await sm_redis.close()

        # Démonstration avec fallback en mémoire (simule Redis non disponible)
        print("\n--- Démonstration avec fallback en mémoire (simule Redis down) ---")
        # Pour forcer le fallback, on peut passer une URL invalide ou arrêter le serveur Redis.
        sm_memory = StateManager("redis://invalid_host:6379", ttl=5) # TTL court pour la démo.
        await sm_memory.initialize()
        session_id_memory = "test_session_memory_456"

        await sm_memory.set_session(session_id_memory, {"user": "Bob", "status": "inactive"})
        await sm_memory.set_pipeline_progress(session_id_memory, "stepA", 0.8)

        session_data_mem = await sm_memory.get_session(session_id_memory)
        print(f"Données de session (Mémoire) : {session_data_mem}")

        progress_data_mem = await sm_memory.get_pipeline_progress(session_id_memory)
        print(f"Progression du pipeline (Mémoire) : {progress_data_mem}")

        print("Attente de l'expiration du cache en mémoire...")
        await asyncio.sleep(6) # Attend que le TTL expire.

        session_data_mem_expired = await sm_memory.get_session(session_id_memory)
        print(f"Données de session (Mémoire, après expiration) : {session_data_mem_expired}")

        await sm_memory.close()

    asyncio.run(demo())