# src/middleware/advanced_rate_limiter.py
from collections import defaultdict
from datetime import datetime, timedelta


class AdvancedRateLimiter:
    def __init__(self):
        self.limits = {
            "default": {"requests": 100, "window": 3600},
            "analysis": {"requests": 20, "window": 3600},
            "generation": {"requests": 50, "window": 3600},
        }
        self.requests = defaultdict(list)

    async def check_limit(self, key: str, category: str = "default") -> bool:
        now = datetime.now()
        limit_config = self.limits.get(category, self.limits["default"])

        # Nettoyer les anciennes requêtes
        cutoff = now - timedelta(seconds=limit_config["window"])
        self.requests[f"{category}:{key}"] = [
            req for req in self.requests[f"{category}:{key}"]
            if req > cutoff
        ]

        # Vérifier la limite
        if len(self.requests[f"{category}:{key}"]) >= limit_config["requests"]:
            return False

        self.requests[f"{category}:{key}"].append(now)
        return True
