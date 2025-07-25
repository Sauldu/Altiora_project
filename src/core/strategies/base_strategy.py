# src/core/strategies/base_strategy.py
"""Module définissant l'interface de base pour toutes les stratégies de workflow.

Ce module établit un contrat pour les classes de stratégie, garantissant
qu'elles implémentent une méthode `execute` asynchrone. Cela permet au
moteur de workflow d'interagir de manière polymorphe avec différentes
stratégies (analyse SFD, génération de tests, etc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class WorkflowStrategy(ABC):
    """Classe abstraite de base pour toutes les stratégies de workflow.

    Toute stratégie concrète doit hériter de cette classe et implémenter
    la méthode `execute`.
    """

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute la logique spécifique de la stratégie.

        Args:
            context: Un dictionnaire contenant les données nécessaires à l'exécution
                     de la stratégie. Le contenu de ce dictionnaire dépend de la
                     stratégie spécifique.

        Returns:
            Un dictionnaire contenant les résultats de l'exécution de la stratégie.
            Le contenu de ce dictionnaire dépend également de la stratégie.

        Raises:
            NotImplementedError: Si la méthode n'est pas implémentée par une sous-classe.
        """
        pass
