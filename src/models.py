# src/models.py
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List

class User(BaseModel):
    id: str
    username: str
    roles: List[str]

class Report(BaseModel):
    id: str
    title: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Test(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))