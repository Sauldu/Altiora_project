# src/auth/main.py
"""
Altiora Auth Service – FastAPI-based JWT auth
100 % PyCharm-clean, ready for v0.1.0
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from src.auth.config import settings  # ✅ centralised settings

from src.auth.jwt_handler import jwt_handler
from src.auth.middleware import get_current_active_user
from src.auth.models import Base, Token, UserCreate, UserResponse
from src.auth.password_utils import is_password_strong
from src.auth.user_service import UserService

# ------------------------------------------------------------------
# DB setup
# ------------------------------------------------------------------
DATABASE_URL = settings.database_url
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


# ------------------------------------------------------------------
# Dependency
# ------------------------------------------------------------------
def get_db() -> Session:
    """Provide DB session for FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------
app = FastAPI(
    title="Altiora Auth Service",
    description="JWT-powered authentication & RBAC",
    version="1.0.0",
)


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
@app.post("/register", response_model=UserResponse)
async def register(
        user: UserCreate,
        db: Session = Depends(get_db),
) -> UserResponse:
    """Register a new user with strong-password policy."""
    ok, msg = is_password_strong(user.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    svc = UserService(db)
    try:
        db_user = svc.create_user(**user.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return UserResponse.model_validate(db_user)  # ✅ Pydantic v2


@app.post("/login", response_model=Token)
async def login(
        form: Annotated[OAuth2PasswordRequestForm, Depends()],
        db: Session = Depends(get_db),
) -> Token:
    """Authenticate user and return access + refresh tokens."""
    svc = UserService(db)
    user = svc.authenticate_user(form.username, form.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if svc.is_user_locked(user):
        raise HTTPException(status_code=423, detail="Account locked")

    payload = {
        "sub": user.username,
        "user_id": user.id,
        "roles": [user.role],
    }
    access_token = jwt_handler.create_access_token(payload)
    return Token(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@app.get("/me", response_model=UserResponse)
async def read_users_me(
        current_user: UserResponse = Depends(get_current_active_user),
) -> UserResponse:
    """Return the current authenticated user."""
    return current_user


@app.post("/refresh", response_model=Token)
async def refresh_access_token(
        refresh_token_str: str,  # ✅ renamed to avoid shadowing
        db: Session = Depends(get_db),
) -> Token:
    """Issue a new access token from a refresh token."""
    token_data = jwt_handler.verify_token(refresh_token_str, token_type="refresh")

    svc = UserService(db)
    user = svc.get_user_by_username(token_data.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_payload = {
        "sub": user.username,
        "user_id": user.id,
        "roles": [user.role],
    }
    access_token = jwt_handler.create_access_token(new_payload)
    return Token(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@app.post("/logout")
async def logout(
        _: UserResponse = Depends(get_current_active_user),
) -> dict[str, str]:
    """Client-side logout – no server state (JWT is stateless)."""
    return {"message": "Successfully logged out"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "src.auth.main:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
