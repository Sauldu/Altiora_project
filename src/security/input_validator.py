# src/security/input_validator.py
"""Module de validation des entrées utilisateur pour renforcer la sécurité.

Ce module fournit des modèles Pydantic et des fonctions utilitaires pour
valider et assainir les données reçues des utilisateurs. Il implémente
des vérifications contre les injections (SQL, NoSQL, shell), l'échappement
HTML, et des limites de taille/profondeur pour prévenir les attaques par
déni de service (DoS) ou les données malformées.
"""

import html
import re
from json import loads, JSONDecodeError
from typing import Dict, Any, List

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, ValidationError, validator


class SFDInput(BaseModel):
    """Modèle de validation pour les entrées de Spécification Fonctionnelle Détaillée (SFD)."""
    content: str = Field(..., max_length=1_000_000, description="Contenu textuel de la SFD (max 1 Mo).")

    @validator("content")
    def escape_html(cls, v: str) -> str:
        """Échappe les caractères HTML pour prévenir les attaques XSS."""
        return html.escape(v)

    @validator("content")
    def block_injection(cls, v: str) -> str:
        """Bloque les motifs d'injection SQL/NoSQL et shell courants.

        Args:
            v: La chaîne de caractères à vérifier.

        Returns:
            La chaîne de caractères si aucun motif d'injection n'est trouvé.

        Raises:
            ValueError: Si un motif d'injection est détecté.
        """
        # Regex pour détecter des mots-clés ou des séquences typiques d'injection.
        blocked_patterns = r"(union|drop|select|insert|update|delete|exec|script|eval|`|system|os\.|subprocess|\b(or|and)\b\s+\d+=\d+|\b(sleep|benchmark)\b)"
        if re.search(blocked_patterns, v, re.IGNORECASE):
            raise ValueError("Motif d'injection détecté dans le contenu.")
        return v

    @validator("content")
    def limit_json_depth_and_keys(cls, v: str) -> str:
        """Limite la profondeur des structures JSON et la longueur des clés pour prévenir les attaques DoS.

        Args:
            v: La chaîne de caractères à vérifier.

        Returns:
            La chaîne de caractères si elle est conforme.

        Raises:
            ValueError: Si la structure JSON est trop profonde ou si les clés sont trop longues.
        """
        try:
            # Tente de parser le contenu comme du JSON.
            parsed = loads(v)
            _check_depth_and_keys(parsed) # Appelle la fonction utilitaire interne.
        except JSONDecodeError:
            pass  # Le contenu n'est pas du JSON, donc cette validation ne s'applique pas.
        return v


class TestGenerationInput(BaseModel):
    """Modèle de validation pour les entrées de génération de tests."""
    sfd_id: str = Field(..., min_length=1, max_length=50, regex=r"^[A-Za-z0-9_-]+$", description="ID de la SFD associée.")
    scenarios: List[str] = Field(..., min_items=1, max_items=100, description="Liste des libellés de scénarios.")

    @validator("scenarios")
    def no_empty_strings(cls, v: List[str]) -> List[str]:
        """Vérifie qu'aucun libellé de scénario n'est vide ou ne contient que des espaces."""
        if any(not s.strip() for s in v):
            raise ValueError("Les libellés de scénario ne peuvent pas être vides.")
        return v


class BatchJobInput(BaseModel):
    """Modèle de validation pour les entrées de tâches par lots."""
    folder: str = Field(..., regex=r"^[A-Za-z0-9_-]{1,64}$", description="Nom du dossier (sans traversal de chemin).")
    max_files: int = Field(..., ge=1, le=1_000, description="Nombre maximal de fichiers à traiter (protection DoS).")


# ------------------------------------------------------------------
# Utilitaire centralisé pour la validation FastAPI
# ------------------------------------------------------------------
def validate_or_422(model: type[BaseModel], data: Dict[str, Any]) -> BaseModel:
    """Valide les données avec un modèle Pydantic ou lève une HTTPException 422.

    Args:
        model: Le modèle Pydantic à utiliser pour la validation.
        data: Le dictionnaire de données à valider.

    Returns:
        Une instance du modèle Pydantic validé.

    Raises:
        HTTPException: Si la validation échoue, avec un statut 422 (Unprocessable Entity).
    """
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
def _check_depth_and_keys(obj: Any, depth: int = 0, max_depth: int = 10):
    """Vérifie la profondeur d'une structure JSON et la longueur des clés.

    Args:
        obj: L'objet JSON (dict ou list) à vérifier.
        depth: La profondeur actuelle de la récursion.
        max_depth: La profondeur maximale autorisée.

    Raises:
        ValueError: Si la profondeur maximale est dépassée ou si une clé est trop longue.
    """
    if depth > max_depth:
        raise ValueError("Profondeur JSON trop élevée. Limite : {max_depth}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if len(k) > 128: # Limite la longueur des clés pour éviter les attaques par hachage.
                raise ValueError("Clé JSON trop longue.")
            _check_depth_and_keys(v, depth + 1, max_depth)
    elif isinstance(obj, list):
        for item in obj:
            _check_depth_and_keys(item, depth + 1, max_depth)


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("\n--- Démonstration de SFDInput ---")
    # Cas valide.
    try:
        sfd_valid = SFDInput(content="<p>Ceci est un test.</p>")
        print(f"SFD valide : {sfd_valid.content}")
    except ValidationError as e:
        logging.error(f"Erreur de validation SFD (attendu valide) : {e.errors()}")

    # Cas avec injection simulée.
    try:
        sfd_injection = SFDInput(content="SELECT * FROM users; DROP TABLE users;")
        print(f"SFD avec injection (ne devrait pas s'afficher) : {sfd_injection.content}")
    except ValidationError as e:
        logging.info(f"SFD avec injection bloquée (attendu) : {e.errors()}")

    # Cas avec JSON trop profond.
    deep_json = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": {"k": "value"}}}}}}}}}}}
    try:
        sfd_deep_json = SFDInput(content=json.dumps(deep_json))
        print(f"SFD JSON profond (ne devrait pas s'afficher) : {sfd_deep_json.content}")
    except ValidationError as e:
        logging.info(f"SFD JSON profond bloqué (attendu) : {e.errors()}")

    print("\n--- Démonstration de TestGenerationInput ---")
    # Cas valide.
    try:
        test_gen_valid = TestGenerationInput(sfd_id="SFD-001", scenarios=["Scenario 1", "Scenario 2"])
        print(f"TestGenerationInput valide : {test_gen_valid}")
    except ValidationError as e:
        logging.error(f"Erreur de validation TestGenerationInput (attendu valide) : {e.errors()}")

    # Cas avec scénario vide.
    try:
        test_gen_empty_scenario = TestGenerationInput(sfd_id="SFD-002", scenarios=["Scenario 1", " "])
        print(f"TestGenerationInput avec scénario vide (ne devrait pas s'afficher) : {test_gen_empty_scenario}")
    except ValidationError as e:
        logging.info(f"TestGenerationInput avec scénario vide bloqué (attendu) : {e.errors()}")

    print("\n--- Démonstration de validate_or_422 (simulée) ---")
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.post("/test_sfd")
    async def test_sfd_endpoint(request: Request):
        data = await request.json()
        validated_data = validate_or_422(SFDInput, data)
        return {"message": "Données SFD reçues et validées", "data": validated_data.model_dump()}

    client = TestClient(app)

    # Test valide.
    response_valid = client.post("/test_sfd", json={"content": "Contenu normal."})
    print(f"Réponse valide (status {response_valid.status_code}) : {response_valid.json()}")

    # Test invalide.
    response_invalid = client.post("/test_sfd", json={"content": "DROP TABLE users;"})
    print(f"Réponse invalide (status {response_invalid.status_code}) : {response_invalid.json()}")