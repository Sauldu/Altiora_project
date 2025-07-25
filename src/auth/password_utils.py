from passlib.context import CryptContext
import secrets
from typing import Tuple


# Configuration du contexte de hachage pour les mots de passe.
# Utilise bcrypt, un algorithme de hachage robuste et recommandé pour les mots de passe.
# `rounds` définit le coût de calcul, plus il est élevé, plus le hachage est lent et sécurisé.
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Nombre de rounds (coût CPU) pour bcrypt.
)


def hash_password(password: str) -> str:
    """Hache un mot de passe en texte clair en utilisant l'algorithme configuré.

    Args:
        password: Le mot de passe en texte clair.

    Returns:
        Le mot de passe haché.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie si un mot de passe en texte clair correspond à un mot de passe haché.

    Args:
        plain_password: Le mot de passe en texte clair fourni par l'utilisateur.
        hashed_password: Le mot de passe haché stocké.

    Returns:
        True si les mots de passe correspondent, False sinon.
    ""
    return pwd_context.verify(plain_password, hashed_password)


def generate_secure_token(length: int = 32) -> str:
    """Génère un jeton sécurisé et difficile à deviner.

    Utilise `secrets.token_urlsafe` pour créer une chaîne de caractères
    adaptée aux URL, utile pour les jetons de réinitialisation de mot de passe,
    les clés API temporaires, etc.

    Args:
        length: La longueur du jeton en octets (la chaîne résultante sera plus longue).

    Returns:
        Un jeton sécurisé sous forme de chaîne de caractères.
    """
    return secrets.token_urlsafe(length)


def is_password_strong(password: str) -> Tuple[bool, str]:
    """Vérifie la force d'un mot de passe selon des critères prédéfinis.

    Args:
        password: Le mot de passe à évaluer.

    Returns:
        Un tuple (bool, str) où le booléen indique si le mot de passe est fort,
        et la chaîne de caractères fournit un message d'erreur si ce n'est pas le cas.
    """
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères."

    if not any(c.isupper() for c in password):
        return False, "Le mot de passe doit contenir au moins une lettre majuscule."

    if not any(c.islower() for c in password):
        return False, "Le mot de passe doit contenir au moins une lettre minuscule."

    if not any(c.isdigit() for c in password):
        return False, "Le mot de passe doit contenir au moins un chiffre."

    if not any(c in "!@#$%^&*(),.?\":{}<>" for c in password):
        return False, "Le mot de passe doit contenir au moins un caractère spécial (!@#$%^&*(),.?\":{}<>)."

    return True, "Le mot de passe est fort."
