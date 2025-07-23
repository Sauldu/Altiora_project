"""
Gestionnaire JWT sécurisé
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from fastapi import HTTPException, status
from pydantic import BaseSettings
from src.security.secrets_manager import SecretsManager
from .models import TokenData


class JWTSettings(BaseSettings):
    """Configuration JWT"""
    JWT_SECRET = SecretsManager.get_secret("JWT_SECRET_KEY")
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    class Config:
        env_file = ".env"


settings = JWTSettings()


class JWTHandler:
    """Gestionnaire de tokens JWT"""

    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = settings.algorithm
        self.access_expire = timedelta(minutes=settings.access_token_expire_minutes)
        self.refresh_expire = timedelta(days=settings.refresh_token_expire_days)

    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Crée un token d'accès"""
        to_encode = data.copy()
        expire = datetime.utcnow() + self.access_expire
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Crée un token de rafraîchissement"""
        to_encode = data.copy()
        expire = datetime.utcnow() + self.refresh_expire
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str, token_type: str = "access") -> TokenData:
        """Vérifie et décode un token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            if payload.get("type") != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )

            username: Optional[str] = payload.get("sub")
            user_id: Optional[int] = payload.get("user_id")

            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )

            return TokenData(
                username=username,
                user_id=user_id,
                roles=payload.get("roles", [])
            )

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )


jwt_handler = JWTHandler()