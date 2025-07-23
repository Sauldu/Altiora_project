# src/audit/models.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(slots=True)
class AuditEvent:
    ts: datetime
    actor: str
    action: Literal["sfd_upload", "test_gen", "admin_command", "pii_detected"]
    resource: str | None = None
    meta: dict | None = None
