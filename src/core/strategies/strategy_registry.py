# src/core/strategies/strategy_registry.py
"""Registre centralisé pour les stratégies de workflow.

Ce module fournit un mécanisme pour enregistrer et récupérer différentes
implémentations de `WorkflowStrategy`. Cela permet au moteur de workflow
de découvrir et d'utiliser dynamiquement les stratégies disponibles
sans avoir de dépendances directes sur leurs implémentations concrètes.
"""

from typing import Dict, Type, List, Optional
from src.core.strategies.base_strategy import WorkflowStrategy


class StrategyRegistry:
    """Un registre de classes de stratégies de workflow.

    Permet d'enregistrer des classes de stratégies sous un nom unique
    et de les récupérer par la suite.
    """
    _strategies: Dict[str, Type[WorkflowStrategy]] = {}

    @classmethod
    def register(cls, name: str, strategy_class: Type[WorkflowStrategy]) -> None:
        """Enregistre une classe de stratégie dans le registre.

        Args:
            name: Le nom unique sous lequel enregistrer la stratégie.
            strategy_class: La classe de stratégie à enregistrer (doit hériter de `WorkflowStrategy`).

        Raises:
            ValueError: Si une stratégie avec le même nom est déjà enregistrée.
        """
        if name in cls._strategies:
            raise ValueError(f"Une stratégie nommée '{name}' est déjà enregistrée.")
        cls._strategies[name] = strategy_class

    @classmethod
    def get(cls, name: str) -> Optional[Type[WorkflowStrategy]]:
        """Récupère une classe de stratégie par son nom.

        Args:
            name: Le nom de la stratégie à récupérer.

        Returns:
            La classe de stratégie si trouvée, sinon None.
        """
        return cls._strategies.get(name)

    @classmethod
    def list(cls) -> List[str]:
        """Liste tous les noms des stratégies enregistrées."

        Returns:
            Une liste de chaînes de caractères, chaque chaîne étant le nom d'une stratégie.
        """
        return list(cls._strategies.keys())


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Définition d'une stratégie de démonstration.
    class DemoStrategy(WorkflowStrategy):
        def __init__(self, message: str):
            self.message = message

        async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
            logging.info(f"Exécution de DemoStrategy avec le message : {self.message}")
            logging.info(f"Contexte reçu : {context}")
            return {"status": "success", "output": f"Processed by {self.message}"}

    # Enregistrement des stratégies.
    StrategyRegistry.register("demo_strategy_A", DemoStrategy)
    logging.info(f"Stratégies enregistrées : {StrategyRegistry.list()}")

    # Tentative d'enregistrer une stratégie avec un nom déjà pris.
    try:
        StrategyRegistry.register("demo_strategy_A", DemoStrategy)
    except ValueError as e:
        logging.error(f"Erreur attendue lors de l'enregistrement : {e}")

    # Récupération et utilisation d'une stratégie.
    async def run_demo():
        retrieved_strategy_class = StrategyRegistry.get("demo_strategy_A")
        if retrieved_strategy_class:
            logging.info(f"Stratégie récupérée : {retrieved_strategy_class.__name__}")
            instance = retrieved_strategy_class(message="Hello from Registry")
            result = await instance.execute({"input": 123})
            logging.info(f"Résultat de l'exécution : {result}")
        else:
            logging.warning("Stratégie 'demo_strategy_A' non trouvée.")

        # Récupération d'une stratégie inexistante.
        non_existent_strategy = StrategyRegistry.get("non_existent")
        if non_existent_strategy is None:
            logging.info("Stratégie 'non_existent' non trouvée (comportement attendu).")

    asyncio.run(run_demo())
