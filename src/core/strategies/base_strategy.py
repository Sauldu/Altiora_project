# src/core/strategies/base_strategy.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class WorkflowStrategy(ABC):
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pass