# src/core/fallback_system.py
"""Module implémentant un système de fallback pour l'exécution d'opérations.

Ce système permet de définir plusieurs stratégies pour une même opération.
En cas d'échec de la stratégie principale, le système tente automatiquement
d'exécuter l'opération avec des stratégies de fallback, selon un ordre de priorité.
"""

from typing import Any, List, Tuple
import logging

logger = logging.getLogger(__name__)


class FallbackSystem:
    """Gère l'exécution d'opérations avec des stratégies de fallback automatiques."""

    def __init__(self):
        """Initialise le système de fallback.

        Les stratégies sont stockées sous forme de tuples (priorité, stratégie).
        Une priorité plus basse signifie une exécution plus précoce.
        """
        self.strategies: List[Tuple[int, Any]] = []

    def add_strategy(self, strategy: Any, priority: int = 0):
        """Ajoute une stratégie de fallback au système.

        Args:
            strategy: L'objet stratégie à ajouter. Il doit implémenter une méthode `execute`.
            priority: La priorité de la stratégie. Les stratégies avec une priorité plus basse
                      seront tentées en premier. Par défaut à 0.
        """
        self.strategies.append((priority, strategy))
        # Trie les stratégies par priorité pour s'assurer de l'ordre d'exécution.
        self.strategies.sort(key=lambda x: x[0])
        logger.info(f"Stratégie ajoutée : {strategy.__class__.__name__} avec priorité {priority}")

    async def execute_with_fallback(self, operation: str, *args: Any, **kwargs: Any) -> Any:
        """Exécute une opération en essayant les stratégies de fallback si nécessaire.

        Args:
            operation: Le nom de l'opération à exécuter (utilisé pour le logging).
            *args: Arguments positionnels à passer à la méthode `execute` de la stratégie.
            **kwargs: Arguments nommés à passer à la méthode `execute` de la stratégie.

        Returns:
            Le résultat de l'exécution de la première stratégie réussie.

        Raises:
            Exception: Si toutes les stratégies échouent.
        """
        errors: List[Tuple[str, str]] = []

        for priority, strategy in self.strategies:
            strategy_name = strategy.__class__.__name__
            logger.info(f"Tentative d'exécution de l'opération '{operation}' avec la stratégie : {strategy_name} (Priorité: {priority})")
            try:
                # Tente d'exécuter l'opération avec la stratégie actuelle.
                result = await strategy.execute(operation, *args, **kwargs)
                logger.info(f"Opération '{operation}' réussie avec la stratégie : {strategy_name}")
                return result
            except Exception as e:
                # Enregistre l'erreur et passe à la stratégie suivante.
                error_msg = str(e)
                errors.append((strategy_name, error_msg))
                logger.warning(f"La stratégie {strategy_name} a échoué pour l'opération '{operation}' : {error_msg}")
                continue

        # Si toutes les stratégies ont échoué, lève une exception.
        logger.error(f"Toutes les stratégies de fallback ont échoué pour l'opération '{operation}'.")
        raise Exception(f"Toutes les stratégies ont échoué pour l'opération '{operation}': {errors}")


# ------------------------------------------------------------------
# Démonstration
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    class PrimaryStrategy:
        async def execute(self, operation: str, data: str) -> str:
            if operation == "process_data":
                if data == "fail_primary":
                    raise ValueError("Échec de la stratégie primaire")
                return f"Primary processed: {data}"
            return ""

    class SecondaryStrategy:
        async def execute(self, operation: str, data: str) -> str:
            if operation == "process_data":
                if data == "fail_secondary":
                    raise ConnectionError("Échec de la stratégie secondaire")
                return f"Secondary processed: {data}"
            return ""

    class TertiaryStrategy:
        async def execute(self, operation: str, data: str) -> str:
            if operation == "process_data":
                return f"Tertiary processed: {data} (always works)"
            return ""

    async def demo():
        fallback_system = FallbackSystem()
        fallback_system.add_strategy(PrimaryStrategy(), priority=1)
        fallback_system.add_strategy(SecondaryStrategy(), priority=2)
        fallback_system.add_strategy(TertiaryStrategy(), priority=3)

        print("\n--- Test 1: Succès de la stratégie primaire ---")
        result1 = await fallback_system.execute_with_fallback("process_data", "hello")
        print(f"Résultat : {result1}")

        print("\n--- Test 2: Échec de la primaire, succès de la secondaire ---")
        result2 = await fallback_system.execute_with_fallback("process_data", "fail_primary")
        print(f"Résultat : {result2}")

        print("\n--- Test 3: Échec de la primaire et secondaire, succès de la tertiaire ---")
        result3 = await fallback_system.execute_with_fallback("process_data", "fail_secondary")
        print(f"Résultat : {result3}")

        print("\n--- Test 4: Toutes les stratégies échouent ---")
        try:
            await fallback_system.execute_with_fallback("process_data", "fail_all")
        except Exception as e:
            print(f"Erreur attendue : {e}")

    asyncio.run(demo())