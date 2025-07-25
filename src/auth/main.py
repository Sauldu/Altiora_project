# src/auth/main.py
"""Service d'authentification principal pour Altiora.

Ce service, basé sur FastAPI, fournit des points de terminaison (endpoints) pour :
- L'enregistrement de nouveaux utilisateurs (`/register`).
- L'authentification et la génération de jetons JWT (`/login`).
- La récupération des informations de l'utilisateur authentifié (`/me`).
- Le rafraîchissement des jetons d'accès (`/refresh`).

Il intègre une base de données SQLAlchemy, une politique de mot de passe fort,
et une limitation de débit pour se protéger contre les attaques par force brute.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

from configs.config_module import get_settings
from src.auth.jwt_handler import jwt_handler
from src.auth.middleware import get_current_active_user
from src.auth.models import Base, Token, UserCreate, UserResponse
from src.auth.password_utils import is_password_strong
from src.auth.user_service import UserService

# ------------------------------------------------------------------
# Configuration de la base de données
# ------------------------------------------------------------------
settings = get_settings()  # Utilise le singleton pour charger la configuration
DATABASE_URL = settings.auth.database_url

# Crée le moteur SQLAlchemy. `check_same_thread` est pour la compatibilité avec SQLite.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Crée une fabrique de sessions pour interagir avec la base de données.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crée toutes les tables définies dans les modèles SQLAlchemy.
Base.metadata.create_all(bind=engine)


# ------------------------------------------------------------------
# Dépendance FastAPI
# ------------------------------------------------------------------
def get_db() -> Session:
    """Dépendance FastAPI pour fournir une session de base de données par requête."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------------------------------------------
# Application FastAPI
# ------------------------------------------------------------------
# Initialise le limiteur de débit.
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Service d'Authentification Altiora",
    description="Service d'authentification et de RBAC basé sur JWT.",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)


# ------------------------------------------------------------------
# Points de terminaison (Routes)
# ------------------------------------------------------------------
@app.post("/register", response_model=UserResponse)
@limiter.limit("10/minute")
async def register(
        user: UserCreate,
        db: Session = Depends(get_db),
) -> UserResponse:
    """Enregistre un nouvel utilisateur avec une politique de mot de passe fort."""
    # Valide la force du mot de passe avant de continuer.
    ok, msg = is_password_strong(user.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    svc = UserService(db)
    try:
        db_user = svc.create_user(**user.model_dump())
    except ValueError as e:
        # Gère les erreurs d'unicité (username/email déjà pris).
        raise HTTPException(status_code=400, detail=str(e))
    return UserResponse.model_validate(db_user)


@app.post("/login", response_model=Token)
@limiter.limit("20/minute") # Un peu plus permissif que l'enregistrement
async def login(
        form: Annotated[OAuth2PasswordRequestForm, Depends()],
        db: Session = Depends(get_db),
) -> Token:
    """Authentifie un utilisateur et retourne un jeton d'accès."""
    svc = UserService(db)
    user = svc.authenticate_user(form.username, form.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Vérifie si le compte est verrouillé.
    if svc.is_user_locked(user):
        raise HTTPException(status_code=423, detail="Le compte est temporairement verrouillé.")

    # Crée le payload du jeton avec les informations de l'utilisateur.
    payload = {
        "sub": user.username,
        "user_id": user.id,
        "roles": [user.role],
    }
    access_token = jwt_handler.create_access_token(payload)
    return Token(
        access_token=access_token,
        expires_in=settings.auth.access_token_expire_minutes * 60,
    )


@app.get("/me", response_model=UserResponse)
@limiter.limit("60/minute")
async def read_users_me(
        current_user: UserResponse = Depends(get_current_active_user),
) -> UserResponse:
    """Retourne les informations de l'utilisateur actuellement authentifié."""
    return current_user


@app.post("/refresh", response_model=Token)
@limiter.limit("10/minute")
async def refresh_access_token(
        refresh_token_str: str,
        db: Session = Depends(get_db),
) -> Token:
    """Émet un nouveau jeton d'accès à partir d'un jeton de rafraîchissement valide."""
    token_data = jwt_handler.verify_token(refresh_token_str, token_type="refresh")

    svc = UserService(db)
    user = svc.get_user_by_username(token_data.username)
    if not user:
        raise HTTPException(status_code=401, detail="Jeton de rafraîchissement invalide")

    new_payload = {
        "sub": user.username,
        "user_id": user.id,
        "roles": [user.role],
    }
    access_token = jwt_handler.create_access_token(new_payload)
    return Token(
        access_token=access_token,
        expires_in=settings.auth.access_token_expire_minutes * 60,
    )


@app.post("/logout")
@limiter.limit("60/minute")
async def logout(
        _: UserResponse = Depends(get_current_active_user),
) -> dict[str, str]:
    """Déconnecte un utilisateur (côté client).
    
    Puisque JWT est sans état, la déconnexion consiste simplement à supprimer
    le jeton côté client. Ce point de terminaison est là pour la complétude de l'API.
    """
    return {"message": "Déconnexion réussie. Veuillez supprimer le jeton côté client."}


@app.get("/health")
@limiter.limit("60/minute")
async def health_check() -> dict[str, str]:
    """Point de terminaison pour la vérification de l'état de santé du service."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# ------------------------------------------------------------------
# Point d'entrée pour Uvicorn
# ------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "src.auth.main:app",
        host=settings.auth.host,
        port=settings.auth.port,
        log_level="info",
        reload=True # Active le rechargement automatique pour le développement
    )
