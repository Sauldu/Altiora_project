# src/audit/audit_logger.py
import datetime
import json

def get_client_ip():
    return "unknown"

def get_session_id():
    return "unknown"


class AuditLogger:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def log_action(self, action: str, user_id: str, details: dict):
        """Enregistre toute action importante avec horodatage"""
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "details": details,
            "ip_address": get_client_ip(),
            "session_id": get_session_id()
        }

        # Stockage dans Redis avec TTL de 90 jours (conformité RGPD)
        key = f"audit:{user_id}:{datetime.utcnow().timestamp()}"
        await self.redis.setex(key, 7776000, json.dumps(audit_entry))
