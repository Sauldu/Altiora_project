# src/auth/middleware.py
"""
FastAPI authentication & RBAC middleware layer.
100 % PyCharm-clean, ready for v0.1.0
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from .jwt_handler import jwt_handler
from .models import TokenData, User, UserRole  # ✅ imported User
from .user_service import UserService

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

# Ajout de CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Dependency stubs (replace with real DB session)
# ------------------------------------------------------------------
def get_db() -> Session:
    """
    Placeholder for FastAPI dependency injection.
    Replace it with your real DB session generator.
    """
    # TODO: Return actual session from dependency_overrides
    raise NotImplementedError("Override get_db() in app startup")


# ------------------------------------------------------------------
# Security scheme
# ------------------------------------------------------------------
security = HTTPBearer()


# ------------------------------------------------------------------
# Current-user helpers
# ------------------------------------------------------------------
async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
) -> TokenData:
    """
    Decode JWT and return TokenData.

    Raises
    ------
    HTTPException(401 | 423)
        If token invalid, user not found, inactive or locked.
    """
    token = credentials.credentials
    token_data = jwt_handler.verify_token(token)

    service = UserService(db)
    user = service.get_user_by_username(token_data.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
        )
    if service.is_user_locked(user):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is locked due to failed login attempts",
        )

    return token_data


async def get_current_active_user(
        token: TokenData = Depends(get_current_user),
        db: Session = Depends(get_db),
) -> User:
    """Return the full User object."""
    return UserService(db).get_user_by_username(token.username)


# ------------------------------------------------------------------
# Role-based guard
# ------------------------------------------------------------------
def require_role(required_role: UserRole) -> Callable[..., TokenData]:
    """
    Factory returning a FastAPI dependency that enforces a role.

    Usage
    -----
    @router.get("/admin")
    def admin_dashboard(current: TokenData = Depends(require_role(UserRole.ADMIN))):
        ...
    """

    def _guard(
            current: TokenData = Depends(get_current_user),
    ) -> TokenData:
        if required_role not in current.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current

    return _guard


# Convenience shortcuts
require_admin = require_role(UserRole.ADMIN)
require_user = require_role(UserRole.USER)
