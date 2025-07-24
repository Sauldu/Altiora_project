# src/core/strategies/sfd_analysis_strategy.py
from src.core.strategies.base_strategy import WorkflowStrategy
from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from typing import Dict, Any
from src.core.strategies.strategy_registry import StrategyRegistry

class SFDAnalysisStrategy(WorkflowStrategy):
    def __init__(self, qwen3: Qwen3OllamaInterface):
        self.qwen3 = qwen3

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        sfd_request = context.get("sfd_request")
        if not sfd_request:
            raise ValueError("SFD request is missing in the context")

        try:
            analysis_result = await self.qwen3.analyze_sfd(sfd_request)
            scenarios = analysis_result.get("scenarios", [])
            if not scenarios:
                return {"status": "no_scenarios", "saved_scenarios": []}

            return {
                "status": "completed",
                "scenarios": scenarios,
                "analysis_result": analysis_result,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to analyze SFD: {e}")

StrategyRegistry.register("sfd_analysis", SFDAnalysisStrategy)
