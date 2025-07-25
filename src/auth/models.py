from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.ext.declarative import declarative_base

# Base déclarative pour les modèles SQLAlchemy.
Base = declarative_base()


class SFDRequest(BaseModel):
    """Modèle Pydantic pour une requête de Spécification Fonctionnelle Détaillée (SFD)."""
    content: str = Field(..., description="Contenu textuel de la SFD.")
    project_id: Optional[str] = Field(None, description="ID du projet associé à la SFD.")

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Valide que le contenu n'est pas vide et ne dépasse pas une certaine taille."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Le contenu ne peut pas être vide.")
        if len(v) > 1_000_000:
            raise ValueError("Le contenu est trop volumineux (max 1 Mo).")
        return v


class UserRole(str, Enum):
    """Énumération des rôles utilisateur disponibles dans le système."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(Base):
    """Modèle SQLAlchemy pour la table des utilisateurs dans la base de données.

    Représente un utilisateur avec ses informations d'authentification et de profil.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(String(20), default=UserRole.USER.value, nullable=False) # Stocke la valeur de l'Enum
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    preferences = Column(Text, nullable=True)  # Stocke les préférences utilisateur au format JSON string


class UserCreate(BaseModel):
    """Modèle Pydantic pour la création d'un nouvel utilisateur."""
    username: str = Field(..., min_length=3, max_length=50, description="Nom d'utilisateur unique.")
    email: EmailStr = Field(..., description="Adresse email unique de l'utilisateur.")
    password: str = Field(..., min_length=8, max_length=128, description="Mot de passe de l'utilisateur.")
    full_name: Optional[str] = Field(None, max_length=100, description="Nom complet de l'utilisateur.")
    role: UserRole = Field(UserRole.USER, description="Rôle de l'utilisateur dans le système.")


class UserLogin(BaseModel):
    """Modèle Pydantic pour les informations de connexion d'un utilisateur."""
    username: str = Field(..., description="Nom d'utilisateur.")
    password: str = Field(..., description="Mot de passe.")


class UserResponse(BaseModel):
    """Modèle Pydantic pour la réponse d'un utilisateur (sans informations sensibles comme le mot de passe).

    Utilisé pour exposer les informations utilisateur via l'API.
    """
    id: int = Field(..., description="ID unique de l'utilisateur.")
    username: str = Field(..., description="Nom d'utilisateur.")
    email: EmailStr = Field(..., description="Adresse email de l'utilisateur.")
    full_name: Optional[str] = Field(None, description="Nom complet de l'utilisateur.")
    role: UserRole = Field(..., description="Rôle de l'utilisateur.")
    is_active: bool = Field(..., description="Statut d'activité du compte.")
    is_verified: bool = Field(..., description="Indique si l'email de l'utilisateur a été vérifié.")
    created_at: datetime = Field(..., description="Date et heure de création du compte.")
    last_login: Optional[datetime] = Field(None, description="Date et heure de la dernière connexion.")

    class Config:
        from_attributes = True # Permet la conversion depuis les modèles SQLAlchemy


class Token(BaseModel):
    """Modèle Pydantic pour la réponse d'un jeton JWT."""
    access_token: str = Field(..., description="Le jeton d'accès JWT.")
    token_type: str = Field("bearer", description="Le type de jeton (toujours 'bearer').")
    expires_in: int = Field(..., description="Durée de validité du jeton en secondes.")


class TokenData(BaseModel):
    """Modèle Pydantic pour les données contenues dans un jeton JWT décodé."""
    username: Optional[str] = Field(None, description="Nom d'utilisateur (sujet du jeton).")
    user_id: Optional[int] = Field(None, description="ID de l'utilisateur.")
    roles: List[str] = Field([], description="Liste des rôles de l'utilisateur.")