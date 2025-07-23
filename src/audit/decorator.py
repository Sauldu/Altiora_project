# src/audit/decorator.py
import datetime
import functools

from src.audit.writer import AsyncAuditWriter

writer = AsyncAuditWriter(Path("logs/audit"))


def audit(action: str):
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            start = datetime.utcnow()
            try:
                result = await fn(*args, **kwargs)
                writer.log(AuditEvent(ts=start, actor=kwargs.get("user_id", "system"), action=action))
                return result
            except Exception as exc:
                writer.log(AuditEvent(ts=start, actor=kwargs.get("user_id", "system"), action="error", meta={"error": str(exc)}))
                raise

        return wrapper

    return decorator
