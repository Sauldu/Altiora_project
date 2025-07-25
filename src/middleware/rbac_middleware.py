# src/middleware/rbac_middleware.py
"""Middleware pour le contrôle d'accès basé sur les rôles (RBAC).

Ce middleware s'intègre aux applications FastAPI pour vérifier les permissions
des utilisateurs avant d'autoriser l'accès à certaines ressources ou actions.
Il utilise un gestionnaire RBAC centralisé pour déterminer si un utilisateur
possède les droits nécessaires.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import HTTPException, status

from src.rbac.manager import RBACManager
from src.rbac.models import User # Assurez-vous que le modèle User est correctement importé.

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Instance globale du gestionnaire RBAC
# ------------------------------------------------------------------
# Le chemin vers le fichier de configuration des rôles (ex: configs/roles.yaml).
# Assurez-vous que ce fichier existe et est correctement configuré.
rbac_manager = RBACManager(Path("configs/roles.yaml"))


async def verify_permission(
    user: User,
    resource: str,
    action: str,
) -> None:
    """Vérifie si un utilisateur a la permission d'effectuer une action sur une ressource."

    Args:
        user: L'objet `User` représentant l'utilisateur authentifié.
        resource: La ressource à laquelle l'accès est demandé (ex: "sfd:analysis", "user:management").
        action: L'action que l'utilisateur tente d'effectuer (ex: "read", "write", "delete").

    Raises:
        HTTPException: Si l'utilisateur n'a pas la permission requise (statut 403 Forbidden).
    """
    logger.debug(f"Vérification de permission pour l'utilisateur '{user.username}' sur ressource '{resource}' avec action '{action}'.")
    if not rbac_manager.has_permission(user, resource, action):
        logger.warning(f"Accès refusé pour l'utilisateur '{user.username}' : permission '{action}' sur '{resource}' manquante.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"L'utilisateur '{user.username}' n'a pas la permission d'effectuer l'action '{action}' sur la ressource '{resource}'."
        )
    logger.debug(f"Accès autorisé pour l'utilisateur '{user.username}'.")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging
    from fastapi import FastAPI, Depends
    from fastapi.security import OAuth2PasswordBearer
    from src.auth.jwt_handler import jwt_handler
    from src.auth.models import User, UserRole, TokenData # Assurez-vous d'importer UserRole

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Crée un fichier roles.yaml factice pour la démonstration.
    temp_roles_file = Path("configs/roles.yaml")
    temp_roles_file.write_text("""
roles:
  - name: admin
    permissions:
      - "user:read"
      - "user:write"
      - "admin:*"
  - name: user
    permissions:
      - "sfd:read"
      - "sfd:write"
  - name: viewer
    permissions:
      - "sfd:read"
""")

    # Re-initialise le rbac_manager avec le fichier factice.
    rbac_manager = RBACManager(temp_roles_file)

    # Simule un utilisateur authentifié (en temps normal, viendrait d'un token JWT).
    async def get_current_user_mock(username: str, roles: List[UserRole]) -> User:
        # Crée un objet User factice pour la démonstration.
        return User(id=1, username=username, email=f"{username}@example.com", hashed_password="hashed", role=roles[0].value) # Utilise .value pour l'Enum

    # Dépendance pour simuler l'utilisateur courant.
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

    async def get_user_admin() -> User:
        return await get_current_user_mock("admin_user", [UserRole.ADMIN])

    async def get_user_normal() -> User:
        return await get_current_user_mock("normal_user", [UserRole.USER])

    async def get_user_viewer() -> User:
        return await get_current_user_mock("viewer_user", [UserRole.VIEWER])

    app = FastAPI()

    @app.get("/admin_only")
    async def admin_only_endpoint(current_user: User = Depends(get_user_admin)):
        await verify_permission(current_user, "admin", "access")
        return {"message": f"Bienvenue, {current_user.username}! Vous avez accès à l'administration."

    @app.get("/sfd_read")
    async def sfd_read_endpoint(current_user: User = Depends(get_user_normal)):
        await verify_permission(current_user, "sfd", "read")
        return {"message": f"Bienvenue, {current_user.username}! Vous pouvez lire les SFD."

    @app.get("/sfd_write")
    async def sfd_write_endpoint(current_user: User = Depends(get_user_normal)):
        await verify_permission(current_user, "sfd", "write")
        return {"message": f"Bienvenue, {current_user.username}! Vous pouvez écrire des SFD."

    async def run_demo_client():
        print("\n--- Démonstration du RBAC Middleware ---")
        from fastapi.testclient import TestClient
        client = TestClient(app)

        print("\nTest 1: Admin accède à /admin_only (attendu: succès)")
        response = client.get("/admin_only", headers={"Authorization": "Bearer fake_token_admin"})
        print(f"Statut: {response.status_code}, Message: {response.json()}")

        print("\nTest 2: Utilisateur normal accède à /admin_only (attendu: échec 403)")
        response = client.get("/admin_only", headers={"Authorization": "Bearer fake_token_user"})
        print(f"Statut: {response.status_code}, Message: {response.json()}")

        print("\nTest 3: Utilisateur normal accède à /sfd_read (attendu: succès)")
        response = client.get("/sfd_read", headers={"Authorization": "Bearer fake_token_user"})
        print(f"Statut: {response.status_code}, Message: {response.json()}")

        print("\nTest 4: Viewer accède à /sfd_write (attendu: échec 403)")
        response = client.get("/sfd_write", headers={"Authorization": "Bearer fake_token_viewer"})
        print(f"Statut: {response.status_code}, Message: {response.json()}")

        print("Démonstration du RBAC Middleware terminée.")

    # Lance le serveur Uvicorn en arrière-plan pour la démo.
    async def run_server_and_client():
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        await asyncio.sleep(1) # Donne le temps au serveur de démarrer.
        await run_demo_client()
        server_task.cancel()

    import uvicorn
    asyncio.run(run_server_and_client())

    # Nettoyage du fichier factice.
    temp_roles_file.unlink(missing_ok=True)
