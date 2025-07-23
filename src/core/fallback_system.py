# src/core/fallback_system.py
class FallbackSystem:
    def __init__(self):
        self.strategies = []

    def add_strategy(self, strategy, priority=0):
        """Ajoute une stratégie de fallback avec priorité"""
        self.strategies.append((priority, strategy))
        self.strategies.sort(key=lambda x: x[0])

    async def execute_with_fallback(self, operation, *args, **kwargs):
        """Exécute avec fallback automatique"""
        errors = []

        for priority, strategy in self.strategies:
            try:
                return await strategy.execute(operation, *args, **kwargs)
            except Exception as e:
                errors.append((strategy.__class__.__name__, str(e)))
                continue

        raise Exception(f"Toutes les stratégies ont échoué: {errors}")