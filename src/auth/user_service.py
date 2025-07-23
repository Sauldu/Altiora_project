"""
Service de gestion des utilisateurs
"""
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy.orm import Session

from .models import User, UserRole
from .password_utils import hash_password, verify_password


class UserService:
    """Service de gestion des utilisateurs"""

    def __init__(self, db: Session):
        self.db = db

    def create_user(self, username: str, email: str, password: str,
                    full_name: Optional[str] = None,
                    role: UserRole = UserRole.USER) -> User:
        """Crée un nouvel utilisateur"""
        # Vérifier l'unicité
        if self.get_user_by_username(username):
            raise ValueError("Username already exists")
        if self.get_user_by_email(email):
            raise ValueError("Email already exists")

        hashed_password = hash_password(password)

        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authentifie un utilisateur"""
        user = self.get_user_by_username(username)
        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            # Enregistrer l'échec
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=30)
            self.db.commit()
            return None

        # Réinitialiser les tentatives en cas de succès
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        self.db.commit()

        return user

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Récupère un utilisateur par username"""
        return self.db.query(User).filter(User.username == username).first()

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Récupère un utilisateur par email"""
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Récupère un utilisateur par ID"""
        return self.db.query(User).filter(User.id == user_id).first()

    def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Met à jour un utilisateur"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        for key, value in kwargs.items():
            if key != "password":
                setattr(user, key, value)

        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(self, user_id: int, new_password: str) -> bool:
        """Change le mot de passe"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.hashed_password = hash_password(new_password)
        user.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def list_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Liste les utilisateurs"""
        return self.db.query(User).offset(skip).limit(limit).all()

    def deactivate_user(self, user_id: int) -> bool:
        """Désactive un utilisateur"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.is_active = False
        self.db.commit()
        return True

    @staticmethod
    def is_user_locked(user: User) -> bool:
        """Vérifie si un utilisateur est verrouillé"""
        if user.locked_until and user.locked_until > datetime.utcnow():
            return True
        return False
