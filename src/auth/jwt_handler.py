# src/auth/jwt_handler.py
"""Gestionnaire de jetons JWT (JSON Web Tokens) sécurisé.

Ce module centralise la création, la vérification et le décodage des jetons JWT
utilisés pour l'authentification et l'autorisation dans l'application.
Il utilise la bibliothèque `PyJWT` et charge sa configuration (clé secrète,
algorithme, durée de vie des jetons) à partir des paramètres de l'application.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import jwt
from fastapi import HTTPException, status

from configs.config_module import get_settings
from src.auth.models import TokenData

# Charge la configuration spécifique à JWT depuis les paramètres globaux.
settings = get_settings().auth


class JWTHandler:
    """Classe encapsulant la logique de manipulation des jetons JWT."""

    def __init__(self):
        """Initialise le gestionnaire avec les paramètres de configuration."""
        self.secret_key = settings.jwt_secret
        self.algorithm = settings.jwt_algorithm
        self.access_expire = timedelta(minutes=settings.access_token_expire_minutes)
        self.refresh_expire = timedelta(days=settings.refresh_token_expire_days)

    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Crée un jeton d'accès JWT.

        Args:
            data: Le dictionnaire de données (payload) à inclure dans le jeton.
                  Doit contenir 'sub' (sujet), 'user_id', et 'roles'.

        Returns:
            Le jeton d'accès encodé sous forme de chaîne de caractères.
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + self.access_expire
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Crée un jeton de rafraîchissement JWT.

        Args:
            data: Le payload à inclure dans le jeton.

        Returns:
            Le jeton de rafraîchissement encodé.
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + self.refresh_expire
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str, token_type: str = "access") -> TokenData:
        """Vérifie et décode un jeton, en s'assurant qu'il est du bon type.

        Args:
            token: Le jeton JWT à vérifier.
            token_type: Le type de jeton attendu ('access' ou 'refresh').

        Raises:
            HTTPException: Si le jeton est invalide, expiré, ou du mauvais type.

        Returns:
            Les données du jeton décodé sous forme d'un objet `TokenData`.
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Vérifie que le type de jeton correspond à celui attendu.
            if payload.get("type") != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Type de jeton invalide"
                )

            username: Optional[str] = payload.get("sub")
            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Contenu du jeton invalide (sujet manquant)"
                )

            return TokenData(
                username=username,
                user_id=payload.get("user_id"),
                roles=payload.get("roles", [])
            )

        except jwt.ExpiredSignatureError:
            # Gère le cas où le jeton a expiré.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Le jeton a expiré"
            )
        except jwt.PyJWTError:
            # Gère toutes les autres erreurs de décodage JWT.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Jeton invalide"
            )


# Crée une instance unique du gestionnaire pour être utilisée dans toute l'application.
jwt_handler = JWTHandler()
