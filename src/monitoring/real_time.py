import json

# src/monitoring/real_time.py
class RealTimeMonitor:
    """Dashboard WebSocket en temps réel"""
    async def stream_metrics(self):
        async for metric in self.metric_generator():
            yield f"data: {json.dumps(metric)}\n\n"