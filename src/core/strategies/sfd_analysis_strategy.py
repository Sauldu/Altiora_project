# src/core/strategies/sfd_analysis_strategy.py
"""Stratégie de workflow pour l'analyse de Spécifications Fonctionnelles Détaillées (SFD).

Cette stratégie utilise l'interface du modèle Qwen3 pour analyser le contenu
d'une SFD et en extraire des scénarios de test structurés. Elle s'intègre
au registre des stratégies pour être utilisable par le moteur de workflow.
"""

from typing import Dict, Any

from src.core.strategies.base_strategy import WorkflowStrategy
from src.core.strategies.strategy_registry import StrategyRegistry
from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from src.models.sfd_models import SFDAnalysisRequest # Assurez-vous que ce modèle est importé


class SFDAnalysisStrategy(WorkflowStrategy):
    """Implémentation de la stratégie pour l'analyse des SFD."""

    def __init__(self, qwen3: Qwen3OllamaInterface):
        """Initialise la stratégie avec une instance de l'interface Qwen3."

        Args:
            qwen3: Une instance de `Qwen3OllamaInterface` utilisée pour l'analyse.
        """
        self.qwen3 = qwen3

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute l'analyse de la SFD et extrait les scénarios de test.

        Args:
            context: Un dictionnaire contenant la clé 'sfd_request', qui doit être
                     une instance de `SFDAnalysisRequest` ou un dictionnaire
                     pouvant être converti en `SFDAnalysisRequest`.

        Returns:
            Un dictionnaire contenant le statut de l'opération, les scénarios extraits,
            et le résultat complet de l'analyse.

        Raises:
            ValueError: Si la requête SFD est manquante dans le contexte.
            RuntimeError: Si l'analyse de la SFD échoue.
        """
        sfd_request_data = context.get("sfd_request")
        if not sfd_request_data:
            raise ValueError("La requête SFD est manquante dans le contexte.")

        # Assurez-vous que sfd_request_data est une instance de SFDAnalysisRequest
        if not isinstance(sfd_request_data, SFDAnalysisRequest):
            # Si c'est un dictionnaire, tente de le convertir.
            try:
                sfd_request = SFDAnalysisRequest(**sfd_request_data)
            except Exception as e:
                raise ValueError(f"Impossible de créer SFDAnalysisRequest à partir du contexte : {e}")
        else:
            sfd_request = sfd_request_data

        try:
            analysis_result = await self.qwen3.analyze_sfd(sfd_request)
            scenarios = analysis_result.get("scenarios", [])

            if not scenarios:
                return {"status": "no_scenarios", "scenarios": [], "analysis_result": analysis_result}

            return {
                "status": "completed",
                "scenarios": scenarios,
                "analysis_result": analysis_result,
            }
        except Exception as e:
            raise RuntimeError(f"Échec de l'analyse de la SFD : {e}")


# Enregistre la stratégie dans le registre pour qu'elle puisse être découverte et utilisée.
StrategyRegistry.register("sfd_analysis", SFDAnalysisStrategy)