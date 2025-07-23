# src/rbac/manager.py
import json
from pathlib import Path
from typing import Dict, List, Optional
from src.rbac.models import Role, Permission, User

class RBACManager:
    def __init__(self, roles_file: Path):
        self.roles_file = roles_file
        self.roles: Dict[str, Role] = {}
        self.permissions: Dict[str, List[Permission]] = {}
        self.load_roles()

    def load_roles(self):
        if self.roles_file.exists():
            data = json.loads(self.roles_file.read_text())
            for role_data in data:
                role = Role(**role_data)
                self.roles[role.name] = role
                self.permissions[role.name] = role.permissions

    def get_role(self, role_name: str) -> Optional[Role]:
        return self.roles.get(role_name)

    def get_permissions(self, role_name: str) -> List[Permission]:
        return self.permissions.get(role_name, [])

    def has_permission(self, user: User, resource: str, action: str) -> bool:
        for role_name in user.roles:
            role = self.get_role(role_name)
            if role:
                for permission in role.permissions:
                    if permission.resource == resource and permission.action == action:
                        return True
        return False