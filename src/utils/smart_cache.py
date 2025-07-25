# src/utils/smart_cache.py
"""Module implémentant un cache intelligent avec gestion de la durée de vie (TTL).

Ce cache est conçu pour stocker les résultats de fonctions coûteuses en calcul
ou en temps, afin d'éviter de les recalculer inutilement. Il supporte la
génération automatique de clés, l'invalidation d'entrées spécifiques et le
nettoyage complet du cache.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Any, Dict, Callable, Awaitable


class SmartCache:
    """Un cache en mémoire avec une durée de vie (TTL) configurable pour chaque entrée."""

    def __init__(self, default_ttl: int = 3600):
        """Initialise le cache intelligent.

        Args:
            default_ttl: La durée de vie par défaut (en secondes) pour les entrées du cache.
                         Par défaut à 3600 secondes (1 heure).
        """
        self._cache: Dict[str, Dict[str, Any]] = {} # Le dictionnaire interne pour stocker les entrées du cache.
        self.default_ttl = default_ttl

    @staticmethod
    def _generate_key(*args: Any, **kwargs: Any) -> str:
        """Génère une clé de cache unique basée sur les arguments de la fonction.

        La clé est un hachage MD5 des arguments positionnels et nommés de la fonction,
        assurant que des appels identiques produisent la même clé.

        Args:
            *args: Arguments positionnels de la fonction.
            **kwargs: Arguments nommés de la fonction.

        Returns:
            Une chaîne de caractères représentant la clé de cache.
        """
        # Sérialise les arguments en JSON pour garantir une représentation cohérente.
        data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()

    async def get_or_compute(self, func: Callable[..., Awaitable[Any]], *args: Any, ttl: Optional[int] = None, **kwargs: Any) -> Any:
        """Tente de récupérer un résultat du cache ; si non trouvé ou expiré, le calcule et le met en cache.

        Args:
            func: La fonction asynchrone dont le résultat doit être mis en cache.
            *args: Arguments positionnels à passer à `func`.
            ttl: Durée de vie spécifique pour cette entrée de cache en secondes.
                 Si None, utilise `default_ttl`.
            **kwargs: Arguments nommés à passer à `func`.

        Returns:
            Le résultat de la fonction (depuis le cache ou calculé).
        """
        key = self._generate_key(func.__name__, *args, **kwargs)

        # Vérifie si l'entrée existe dans le cache et n'a pas expiré.
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() < entry["expires_at"]:
                return entry["value"]

        # Si non trouvé ou expiré, calcule le résultat en appelant la fonction.
        value = await func(*args, **kwargs)
        expires_at = datetime.now() + timedelta(seconds=ttl or self.default_ttl)

        # Stocke le nouveau résultat dans le cache.
        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": datetime.now()
        }

        return value

    def invalidate(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Invalide une entrée spécifique du cache.

        Args:
            func: La fonction associée à l'entrée à invalider.
            *args: Arguments positionnels utilisés pour générer la clé.
            **kwargs: Arguments nommés utilisés pour générer la clé.
        """
        key = self._generate_key(func.__name__, *args, **kwargs)
        if key in self._cache:
            del self._cache[key]

    def clear_all(self) -> None:
        """Vide complètement le cache."""
        self._cache.clear()


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def expensive_function(param1: str, param2: int) -> str:
        """Une fonction coûteuse qui simule un délai et retourne un résultat."""
        logging.info(f"Calcul de expensive_function({param1}, {param2})...")
        await asyncio.sleep(1) # Simule un travail long.
        return f"Résultat pour {param1}-{param2} à {datetime.now().strftime('%H:%M:%S')}"

    async def demo_smart_cache():
        print("\n--- Démonstration du SmartCache ---")
        cache = SmartCache(default_ttl=5) # TTL par défaut de 5 secondes.

        # Premier appel : le résultat est calculé et mis en cache.
        print("Premier appel (calculé) :")
        result1 = await cache.get_or_compute(expensive_function, "alpha", 1)
        print(f"-> {result1}")

        # Deuxième appel immédiat : le résultat est récupéré du cache.
        print("\nDeuxième appel (depuis cache) :")
        result2 = await cache.get_or_compute(expensive_function, "alpha", 1)
        print(f"-> {result2}")

        # Appel avec des arguments différents : nouveau calcul et mise en cache.
        print("\nTroisième appel (nouveaux arguments, calculé) :")
        result3 = await cache.get_or_compute(expensive_function, "beta", 2)
        print(f"-> {result3}")

        # Attente de l'expiration du cache.
        print("\nAttente de l'expiration du cache (5 secondes)...")
        await asyncio.sleep(5.1)

        # Appel après expiration : le résultat est recalculé.
        print("\nAppel après expiration (recalculé) :")
        result4 = await cache.get_or_compute(expensive_function, "alpha", 1)
        print(f"-> {result4}")

        # Invalidation manuelle.
        print("\nInvalidation manuelle de 'beta'-2...")
        cache.invalidate(expensive_function, "beta", 2)
        print("Appel après invalidation (recalculé) :")
        result5 = await cache.get_or_compute(expensive_function, "beta", 2)
        print(f"-> {result5}")

        # Nettoyage complet du cache.
        print("\nNettoyage complet du cache.")
        cache.clear_all()
        print(f"Cache vide : {cache._cache}")

        print("Démonstration du SmartCache terminée.")

    asyncio.run(demo_smart_cache())
