# src/monitoring/dashboard.py

import datetime
import psutil

class PerformanceDashboard:
    def __init__(self):
        self.metrics = {
            "sfd_processing_time": [],
            "test_generation_time": [],
            "memory_usage": [],
            "cpu_usage": [],
            "error_rate": 0,
            "success_rate": 0
        }

    async def collect_metrics(self):
        """Collecte les métriques en temps réel"""
        return {
            "timestamp": datetime.utcnow(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_mb": psutil.virtual_memory().used / 1024 / 1024,
            "active_connections": await self.count_active_connections(),
            "queue_size": await self.get_queue_size()
        }