# src/security/input_validator.py
import html
import re
from json import loads, JSONDecodeError
from typing import Dict, Any, List

from fastapi import HTTPException, status
from pydantic import BaseModel, validator, ValidationError, Field


class SFDInput(BaseModel):
    content: str = Field(..., max_length=1_000_000)  # 1 Mo max

    # 1️⃣ Échappement HTML de base
    @validator("content")
    def escape_html(cls, v: str) -> str:
        return html.escape(v)

    # 2️⃣ Blocage des patterns d'injection SQL/NoSQL et shell
    @validator("content")
    def block_injection(cls, v: str) -> str:
        blocked = re.search(
            r"(union|drop|select|insert|update|delete|exec|script|eval|`|system|os\.|subprocess)",
            v,
            re.IGNORECASE,
        )
        if blocked:
            raise ValueError("Motif d'injection détecté")
        return v

    # 3️⃣ Limite de profondeur JSON et longueur des clés
    @validator("content")
    def limit_json_depth_and_keys(cls, v: str) -> str:
        try:
            parsed = loads(v)
            _check_depth_and_keys(parsed)
        except JSONDecodeError:
            pass  # Pas du JSON, on laisse passer
        return v


class TestGenerationInput(BaseModel):
    sfd_id: str = Field(..., min_length=1, max_length=50, regex=r"^[A-Za-z0-9_-]+$")
    scenarios: List[str] = Field(..., min_items=1, max_items=100)

    @validator("scenarios")
    def no_empty_strings(cls, v: List[str]) -> List[str]:
        if any(not s.strip() for s in v):
            raise ValueError("Libellé de scénario vide interdit")
        return v


class BatchJobInput(BaseModel):
    folder: str = Field(..., regex=r"^[A-Za-z0-9_-]{1,64}$")  # Pas de traversal
    max_files: int = Field(..., ge=1, le=1_000)  # Protection DOS


# ------------------------------------------------------------------
# Utilitaire centralisé
# ------------------------------------------------------------------
def validate_or_422(model: type[BaseModel], data: Dict[str, Any]) -> BaseModel:
    """Valide les données avec Pydantic ou lève une 422."""
    try:
        return model(**data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(),
        )


# ------------------------------------------------------------------
# Fonction interne pour vérifier la profondeur JSON
# ------------------------------------------------------------------
def _check_depth_and_keys(obj, depth=0, max_depth=10):
    if depth > max_depth:
        raise ValueError("Profondeur JSON trop élevée")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if len(k) > 128:
                raise ValueError("Clé JSON trop longue")
            _check_depth_and_keys(v, depth + 1, max_depth)
    elif isinstance(obj, list):
        for item in obj:
            _check_depth_and_keys(item, depth + 1, max_depth)
