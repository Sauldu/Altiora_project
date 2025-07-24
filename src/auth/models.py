"""
Modèles d'authentification utilisateur
"""
from datetime import datetime
from enum import Enum
from typing import List
from typing import Optional

from pydantic import BaseModel, validator, field_validator
from pydantic import EmailStr, Field
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SFDRequest(BaseModel):
    content: str
    project_id: Optional[str] = None

    @field_validator('content')
    def validate_content(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Content cannot be empty")
        if len(v) > 1_000_000:
            raise ValueError("Content too large")
        return v


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(Base):
    """Table des utilisateurs"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(String(20), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    preferences = Column(Text, nullable=True)  # JSON string


class UserCreate(BaseModel):
    """Modèle de création utilisateur"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=100)
    role: UserRole = UserRole.USER


class UserLogin(BaseModel):
    """Modèle de connexion"""
    username: str
    password: str


class UserResponse(BaseModel):
    """Réponse utilisateur (sans mot de passe)"""
    id: int
    username: str
    email: EmailStr
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]


class Token(BaseModel):
    """Modèle de token JWT"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Données du token"""
    username: Optional[str] = None
    user_id: Optional[int] = None
    roles: List[str] = []
