# src/rbac/manager.py
"""Module de gestion du contrôle d'accès basé sur les rôles (RBAC).

Ce module fournit une classe `RBACManager` qui charge les définitions de rôles
et de permissions à partir d'un fichier de configuration. Il permet de vérifier
si un utilisateur, identifié par ses rôles, a la permission d'effectuer une
action spécifique sur une ressource donnée.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.rbac.models import Role, Permission, User

logger = logging.getLogger(__name__)


class RBACManager:
    """Gère les rôles, les permissions et les vérifications d'accès."""

    def __init__(self, roles_file: Path):
        """Initialise le gestionnaire RBAC."

        Args:
            roles_file: Le chemin vers le fichier JSON ou YAML contenant les définitions de rôles et permissions.
        """
        self.roles_file = roles_file
        self.roles: Dict[str, Role] = {} # Stocke les objets Role par leur nom.
        self.permissions: Dict[str, List[Permission]] = {} # Cache les permissions par rôle.
        self.load_roles()

    def load_roles(self):
        """Charge les définitions de rôles et de permissions depuis le fichier de configuration."

        Cette méthode est appelée à l'initialisation du gestionnaire.
        """
        if not self.roles_file.exists():
            logger.error(f"Fichier de rôles non trouvé : {self.roles_file}. Le RBAC sera désactivé ou incomplet.")
            return
        try:
            # Charge le fichier JSON/YAML.
            # Supposons que le fichier est un JSON pour l'instant.
            with open(self.roles_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for role_data in data.get("roles", []):
                role = Role(**role_data)
                self.roles[role.name] = role
                self.permissions[role.name] = role.permissions
            logger.info(f"Rôles chargés avec succès depuis {self.roles_file}. Nombre de rôles : {len(self.roles)}")
        except (IOError, OSError, json.JSONDecodeError) as e:
            logger.critical(f"Erreur lors du chargement du fichier de rôles {self.roles_file}: {e}")

    def get_role(self, role_name: str) -> Optional[Role]:
        """Récupère un objet `Role` par son nom."

        Args:
            role_name: Le nom du rôle.

        Returns:
            L'objet `Role` si trouvé, sinon None.
        """
        return self.roles.get(role_name)

    def get_permissions(self, role_name: str) -> List[Permission]:
        """Récupère la liste des permissions associées à un rôle."

        Args:
            role_name: Le nom du rôle.

        Returns:
            Une liste d'objets `Permission`.
        """
        return self.permissions.get(role_name, [])

    def has_permission(self, user: User, resource: str, action: str) -> bool:
        """Vérifie si un utilisateur a la permission d'effectuer une action sur une ressource."

        Args:
            user: L'objet `User` représentant l'utilisateur.
            resource: La ressource à laquelle l'accès est demandé (ex: "sfd:analysis").
            action: L'action que l'utilisateur tente d'effectuer (ex: "read", "write").

        Returns:
            True si l'utilisateur a la permission, False sinon.
        """
        for role_name in user.roles:
            role = self.get_role(role_name)
            if role:
                for permission in role.permissions:
                    # Vérifie si la permission correspond exactement ou si c'est un joker.
                    if (permission.resource == resource or permission.resource == "*") and \
                       (permission.action == action or permission.action == "*"):
                        logger.debug(f"Permission accordée pour {user.username} via rôle {role_name}: {resource}:{action}")
                        return True
        logger.debug(f"Permission refusée pour {user.username}: {resource}:{action}")
        return False


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Crée un fichier de rôles factice pour la démonstration.
    temp_roles_file = Path("temp_roles.json")
    temp_roles_file.write_text("""
{
  "roles": [
    {
      "name": "admin",
      "permissions": [
        {"resource": "user", "action": "*"},
        {"resource": "system", "action": "shutdown"}
      ]
    },
    {
      "name": "editor",
      "permissions": [
        {"resource": "document", "action": "read"},
        {"resource": "document", "action": "write"}
      ]
    },
    {
      "name": "viewer",
      "permissions": [
        {"resource": "document", "action": "read"}
      ]
    }
  ]
}
""")

    print("\n--- Démonstration du RBACManager ---")
    manager = RBACManager(temp_roles_file)

    # Utilisateurs de démonstration.
    admin_user = User(id="admin_1", roles=["admin"])
    editor_user = User(id="editor_1", roles=["editor"])
    viewer_user = User(id="viewer_1", roles=["viewer"])
    guest_user = User(id="guest_1", roles=["unknown_role"])

    print("\n--- Vérification des permissions ---")
    # Admin permissions.
    print(f"Admin peut éteindre le système : {manager.has_permission(admin_user, 'system', 'shutdown')}")
    print(f"Admin peut lire les utilisateurs : {manager.has_permission(admin_user, 'user', 'read')}")

    # Editor permissions.
    print(f"Editor peut écrire un document : {manager.has_permission(editor_user, 'document', 'write')}")
    print(f"Editor peut éteindre le système : {manager.has_permission(editor_user, 'system', 'shutdown')}")

    # Viewer permissions.
    print(f"Viewer peut lire un document : {manager.has_permission(viewer_user, 'document', 'read')}")
    print(f"Viewer peut écrire un document : {manager.has_permission(viewer_user, 'document', 'write')}")

    # Guest permissions.
    print(f"Guest peut lire un document : {manager.has_permission(guest_user, 'document', 'read')}")

    print("Démonstration du RBACManager terminée.")

    # Nettoyage du fichier factice.
    temp_roles_file.unlink(missing_ok=True)
