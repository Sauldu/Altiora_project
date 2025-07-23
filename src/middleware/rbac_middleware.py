# src/middleware/rbac_middleware.py
from __future__ import annotations

from pathlib import Path   # ✅  Fixed missing import

from fastapi import HTTPException

from src.rbac.manager import RBACManager
from src.rbac.models import User

# ------------------------------------------------------------------
# Global RBAC instance
# ------------------------------------------------------------------
rbac_manager = RBACManager(Path("configs/roles.yaml"))


async def verify_permission(
    user: User,
    resource: str,
    action: str,
) -> None:
    """
    Fast-path permission check.

    Raises
    ------
    HTTPException(403)
        If access is denied.
    """
    if not rbac_manager.has_permission(user, resource, action):
        raise HTTPException(
            status_code=403,
            detail=f"User '{user.id}' lacks permission '{action}' on '{resource}'",
        )