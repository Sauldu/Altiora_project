# src/utils/smart_cache.py
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
import hashlib
import json


class SmartCache:
    def __init__(self, default_ttl: int = 3600):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl

    @staticmethod
    def _generate_key(*args, **kwargs) -> str:
        data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()

    async def get_or_compute(self, func, *args, ttl: Optional[int] = None, **kwargs):
        key = self._generate_key(func.__name__, *args, **kwargs)

        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() < entry["expires_at"]:
                return entry["value"]

        value = await func(*args, **kwargs)
        expires_at = datetime.now() + timedelta(seconds=ttl or self.default_ttl)

        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": datetime.now()
        }

        return value