from typing import Dict, Type
from src.core.strategies.base_strategy import WorkflowStrategy

class StrategyRegistry:
    _strategies: Dict[str, Type[WorkflowStrategy]] = {}

    @classmethod
    def register(cls, name: str, strategy_class: Type[WorkflowStrategy]) -> None:
        cls._strategies[name] = strategy_class

    @classmethod
    def get(cls, name: str) -> Type[WorkflowStrategy] | None:
        return cls._strategies.get(name)

    @classmethod
    def list(cls) -> list[str]:
        return list(cls._strategies.keys())