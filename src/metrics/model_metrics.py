# src/metrics/model_metrics.py
class ModelMetrics:
    def __init__(self):
        self.accuracy_tracker = AccuracyTracker()
        self.latency_monitor = LatencyMonitor()
        self.token_usage = TokenUsageTracker()

    def evaluate_model_performance(self, model_name: str):
        """Évalue les performances du modèle fine-tuné"""
        metrics = {
            'perplexity': self.calculate_perplexity(),
            'bleu_score': self.calculate_bleu(),
            'response_time_p95': self.latency_monitor.get_p95(),
            'tokens_per_second': self.token_usage.get_throughput()
        }
        return metrics