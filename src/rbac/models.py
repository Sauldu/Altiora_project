# src/rbac/models.py
from typing import List

from pydantic import BaseModel


class Permission(BaseModel):
    resource: str
    action: str


class Role(BaseModel):
    name: str
    permissions: List[Permission]


class User(BaseModel):
    id: str
    roles: List[str]
