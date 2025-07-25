# src/scaling/auto_scaler.py
"""Module implémentant un auto-scaler intelligent basé sur l'apprentissage automatique.

Ce module fournit une logique de décision pour l'ajustement dynamique des
ressources (mise à l'échelle horizontale ou verticale) en fonction de la
charge prédite. Il utilise des métriques collectées et un prédicteur de charge
pour anticiper les besoins et optimiser l'utilisation des ressources.
"""

import logging
from enum import Enum
from typing import Any, Dict

logger = logging.getLogger(__name__)


# --- Classes factices pour la démonstration et la documentation --- #
class ScaleAction(Enum):
    """Actions de mise à l'échelle possibles."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_CHANGE = "no_change"


class MetricsCollector:
    """Collecteur de métriques factice."""
    async def get_current(self) -> Dict[str, Any]:
        """Simule la récupération des métriques actuelles."""
        logger.info("Collecte des métriques actuelles...")
        await asyncio.sleep(0.1) # Simule un délai.
        return {"cpu_usage": 0.6, "memory_usage": 0.7, "request_rate": 150}


class LoadPredictor:
    """Prédicteur de charge factice basé sur l'apprentissage automatique."""
    async def predict_next_hour(self, current_metrics: Dict[str, Any]) -> float:
        """Simule la prédiction de la charge pour la prochaine heure."""
        logger.info(f"Prédiction de la charge pour la prochaine heure basée sur : {current_metrics}")
        await asyncio.sleep(0.2) # Simule un délai.
        # Logique de prédiction factice.
        if current_metrics.get("request_rate", 0) > 100:
            return 0.9 # Charge élevée.
        return 0.4 # Charge faible.


# --- Auto-scaler intelligent --- #
class IntelligentAutoScaler:
    """Décide des actions de mise à l'échelle basées sur les métriques et la prédiction de charge."""

    def __init__(self, high_threshold: float = 0.8, low_threshold: float = 0.3):
        """Initialise l'auto-scaler intelligent."

        Args:
            high_threshold: Seuil de charge au-delà duquel une mise à l'échelle ascendante est déclenchée.
            low_threshold: Seuil de charge en dessous duquel une mise à l'échelle descendante est déclenchée.
        """
        self.metrics_collector = MetricsCollector()
        self.predictor = LoadPredictor()
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        logger.info(f"IntelligentAutoScaler initialisé. Seuil haut: {high_threshold}, Seuil bas: {low_threshold}.")

    async def scale_decision(self) -> ScaleAction:
        """Prend une décision de mise à l'échelle basée sur les métriques actuelles et la charge prédite."

        Returns:
            Une `ScaleAction` indiquant si le système doit monter en charge, descendre en charge, ou rester stable.
        """
        logger.info("Prise de décision de mise à l'échelle...")
        current_metrics = await self.metrics_collector.get_current()
        predicted_load = await self.predictor.predict_next_hour(current_metrics)

        logger.info(f"Charge prédite pour la prochaine heure : {predicted_load:.2f}")

        if predicted_load > self.high_threshold:
            logger.info("Décision : Mise à l'échelle ascendante (SCALE_UP).")
            return ScaleAction.SCALE_UP
        elif predicted_load < self.low_threshold:
            logger.info("Décision : Mise à l'échelle descendante (SCALE_DOWN).")
            return ScaleAction.SCALE_DOWN
        else:
            logger.info("Décision : Pas de changement (NO_CHANGE).")
            return ScaleAction.NO_CHANGE


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def demo():
        print("\n--- Démonstration de l'IntelligentAutoScaler ---")
        scaler = IntelligentAutoScaler(high_threshold=0.7, low_threshold=0.4)

        print("\nPremière décision de scaling...")
        decision1 = await scaler.scale_decision()
        print(f"Décision prise : {decision1.value}")

        # Simule une charge élevée pour forcer un SCALE_UP.
        class MockHighLoadPredictor(LoadPredictor):
            async def predict_next_hour(self, current_metrics: Dict[str, Any]) -> float:
                return 0.9
        scaler.predictor = MockHighLoadPredictor()

        print("\nDeuxième décision de scaling (charge élevée simulée)...")
        decision2 = await scaler.scale_decision()
        print(f"Décision prise : {decision2.value}")

        # Simule une charge faible pour forcer un SCALE_DOWN.
        class MockLowLoadPredictor(LoadPredictor):
            async def predict_next_hour(self, current_metrics: Dict[str, Any]) -> float:
                return 0.2
        scaler.predictor = MockLowLoadPredictor()

        print("\nTroisième décision de scaling (charge faible simulée)...")
        decision3 = await scaler.scale_decision()
        print(f"Décision prise : {decision3.value}")

        print("Démonstration de l'auto-scaler terminée.")

    asyncio.run(demo())