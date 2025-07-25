# src/rbac/models.py
"""Modèles de données pour le contrôle d'accès basé sur les rôles (RBAC).

Ce module définit les structures de données Pydantic pour représenter
les permissions, les rôles et les utilisateurs dans le système RBAC.
Ces modèles garantissent la validation et la cohérence des données
utilisées pour la gestion des accès.
"""

from typing import List

from pydantic import BaseModel, Field


class Permission(BaseModel):
    """Représente une permission spécifique dans le système."

    Une permission est définie par une ressource et une action.
    Exemples: {"resource": "document", "action": "read"}, {"resource": "user", "action": "create"}
    """
    resource: str = Field(..., description="La ressource à laquelle la permission s'applique (ex: 'document', 'user', '*').")
    action: str = Field(..., description="L'action autorisée sur la ressource (ex: 'read', 'write', 'delete', '*').")


class Role(BaseModel):
    """Représente un rôle dans le système RBAC."

    Un rôle est un ensemble de permissions.
    Exemples: {"name": "admin", "permissions": [...]}, {"name": "viewer", "permissions": [...]}
    """
    name: str = Field(..., description="Le nom unique du rôle (ex: 'admin', 'editor', 'viewer').")
    permissions: List[Permission] = Field(..., description="La liste des permissions associées à ce rôle.")


class User(BaseModel):
    """Représente un utilisateur dans le contexte du RBAC."

    Un utilisateur est identifié par un ID et possède une liste de rôles.
    """
    id: str = Field(..., description="L'identifiant unique de l'utilisateur.")
    roles: List[str] = Field(..., description="La liste des noms de rôles assignés à l'utilisateur.")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("\n--- Démonstration des modèles RBAC ---")

    # Création de permissions.
    perm_read_doc = Permission(resource="document", action="read")
    perm_write_doc = Permission(resource="document", action="write")
    perm_all_users = Permission(resource="user", action="*")
    perm_shutdown_system = Permission(resource="system", action="shutdown")

    print(f"Permission de lecture de document : {perm_read_doc}")

    # Création de rôles.
    role_viewer = Role(name="viewer", permissions=[perm_read_doc])
    role_editor = Role(name="editor", permissions=[perm_read_doc, perm_write_doc])
    role_admin = Role(name="admin", permissions=[perm_all_users, perm_shutdown_system])

    print(f"\nRôle Viewer : {role_viewer}")
    print(f"Rôle Editor : {role_editor}")
    print(f"Rôle Admin : {role_admin}")

    # Création d'utilisateurs.
    user_alice = User(id="alice_123", roles=["viewer"])
    user_bob = User(id="bob_456", roles=["editor"])
    user_charlie = User(id="charlie_789", roles=["admin"])

    print(f"\nUtilisateur Alice : {user_alice}")
    print(f"Utilisateur Bob : {user_bob}")
    print(f"Utilisateur Charlie : {user_charlie}")

    # Exemple de validation (Pydantic lève une erreur si les données sont invalides).
    try:
        invalid_permission = Permission(resource="", action="")
    except Exception as e:
        print(f"\nErreur de validation attendue pour une permission invalide : {e}")

    print("Démonstration des modèles RBAC terminée.")