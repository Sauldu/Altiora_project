# src/audit/ring_buffer.py
import json
from collections import deque


class RingBuffer:
    def __init__(self, size: int = 10_000):
        self._buf: deque[str] = deque(maxlen=size)

    def push(self, event: AuditEvent) -> None:
        self._buf.append(json.dumps(asdict(event), default=str))

    def flush(self) -> list[str]:
        out = list(self._buf)
        self._buf.clear()
        return out
