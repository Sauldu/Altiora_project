# src/scaling/auto_scaler.py
class IntelligentAutoScaler:
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.predictor = LoadPredictor()

    async def scale_decision(self):
        """Décision de scaling basée sur ML"""
        current_metrics = await self.metrics_collector.get_current()
        predicted_load = self.predictor.predict_next_hour(current_metrics)

        if predicted_load > self.high_threshold:
            return ScaleAction.SCALE_UP
        elif predicted_load < self.low_threshold:
            return ScaleAction.SCALE_DOWN

        return ScaleAction.NO_CHANGE