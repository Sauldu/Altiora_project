from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy.orm import Session

from .models import User, UserRole
from .password_utils import hash_password, verify_password


class UserService:
    """Service de gestion des utilisateurs.

    Cette classe encapsule la logique métier pour la création, l'authentification,
    la récupération et la modification des utilisateurs dans la base de données.
    Elle interagit avec les modèles SQLAlchemy et les utilitaires de mot de passe.
    """

    def __init__(self, db: Session):
        """Initialise le service utilisateur avec une session de base de données."""
        self.db = db

    def create_user(self, username: str, email: str, password: str,
                    full_name: Optional[str] = None,
                    role: UserRole = UserRole.USER) -> User:
        """Crée un nouvel utilisateur dans la base de données.

        Args:
            username: Le nom d'utilisateur unique.
            email: L'adresse email unique de l'utilisateur.
            password: Le mot de passe en texte clair (sera haché avant stockage).
            full_name: Le nom complet de l'utilisateur (optionnel).
            role: Le rôle de l'utilisateur (par défaut UserRole.USER).

        Returns:
            L'objet `User` nouvellement créé.

        Raises:
            ValueError: Si le nom d'utilisateur ou l'email existe déjà.
        """
        # Vérifie l'unicité du nom d'utilisateur et de l'email.
        if self.get_user_by_username(username):
            raise ValueError("Le nom d'utilisateur existe déjà.")
        if self.get_user_by_email(email):
            raise ValueError("L'adresse email existe déjà.")

        hashed_password = hash_password(password)

        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role.value # Stocke la valeur de l'Enum
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authentifie un utilisateur en vérifiant le nom d'utilisateur et le mot de passe.

        Gère également les tentatives de connexion échouées et le verrouillage du compte.

        Args:
            username: Le nom d'utilisateur.
            password: Le mot de passe en texte clair.

        Returns:
            L'objet `User` si l'authentification réussit, None sinon.
        """
        user = self.get_user_by_username(username)
        if not user:
            return None

        # Vérifie le mot de passe.
        if not verify_password(password, user.hashed_password):
            # Incrémente le compteur d'échecs et verrouille le compte si trop de tentatives.
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=30) # Verrouille pour 30 minutes
            self.db.commit()
            return None

        # Réinitialise les tentatives d'échec et met à jour la dernière connexion en cas de succès.
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        self.db.commit()

        return user

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Récupère un utilisateur par son nom d'utilisateur."""
        return self.db.query(User).filter(User.username == username).first()

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Récupère un utilisateur par son adresse email."""
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Récupère un utilisateur par son ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Met à jour les informations d'un utilisateur.

        Args:
            user_id: L'ID de l'utilisateur à mettre à jour.
            **kwargs: Les champs à mettre à jour (ex: full_name="Nouveau Nom").

        Returns:
            L'objet `User` mis à jour, ou None si l'utilisateur n'existe pas.
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        for key, value in kwargs.items():
            # Empêche la mise à jour directe du mot de passe via cette méthode.
            if key != "password":
                setattr(user, key, value)

        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(self, user_id: int, new_password: str) -> bool:
        """Change le mot de passe d'un utilisateur.

        Args:
            user_id: L'ID de l'utilisateur.
            new_password: Le nouveau mot de passe en texte clair.

        Returns:
            True si le mot de passe a été changé avec succès, False sinon.
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.hashed_password = hash_password(new_password)
        user.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def list_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Liste les utilisateurs avec pagination.

        Args:
            skip: Nombre d'utilisateurs à ignorer (offset).
            limit: Nombre maximal d'utilisateurs à retourner.

        Returns:
            Une liste d'objets `User`.
        """
        return self.db.query(User).offset(skip).limit(limit).all()

    def deactivate_user(self, user_id: int) -> bool:
        """Désactive un utilisateur (le rend inactif).

        Args:
            user_id: L'ID de l'utilisateur à désactiver.

        Returns:
            True si l'utilisateur a été désactivé, False sinon.
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.is_active = False
        self.db.commit()
        return True

    @staticmethod
    def is_user_locked(user: User) -> bool:
        """Vérifie si un compte utilisateur est actuellement verrouillé.

        Args:
            user: L'objet `User` à vérifier.

        Returns:
            True si le compte est verrouillé, False sinon.
        """
        if user.locked_until and user.locked_until > datetime.utcnow():
            return True
        return False