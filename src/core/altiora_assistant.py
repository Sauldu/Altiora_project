# src/core/altiora_assistant.py
"""Module définissant une façade de haut niveau pour interagir avec l'assistant Altiora.

Ce module fournit la classe `AltioraQAAssistant`, qui simplifie l'utilisation
de l'orchestrateur et des autres composants du système. Elle est conçue pour
être le point d'entrée principal pour les interfaces utilisateur (CLI, UI web)
ou les points d'accès API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from configs.settings_loader import get_settings

from src.infrastructure.redis_config import get_redis_client
from src.models.sfd_models import SFDAnalysisRequest
from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Contexte de session
# ------------------------------------------------------------------

@dataclass
class QAContext:
    """Représente le contexte d'une session d'interaction avec l'assistant.

    Attributes:
        user_id: L'identifiant de l'utilisateur.
        project_name: Le nom du projet en cours.
        session_id: Un identifiant unique pour la session.
        created_at: La date et l'heure de création de la session.
    """
    user_id: str
    project_name: str
    session_id: str
    created_at: datetime


class AltioraQAAssistant:
    """Façade de haut niveau pour interagir avec les fonctionnalités de QA d'Altiora.

    Cette classe est conçue pour être utilisée comme un gestionnaire de contexte
    asynchrone (`async with`). Elle gère le cycle de vie de l'orchestrateur et
    maintient un contexte de session.

    Exemple d'utilisation:
    ```python
    async with AltioraQAAssistant() as assistant:
        await assistant.start_session(user_id="dev")
        results = await assistant.run_full_pipeline("path/to/sfd.txt")
        print(results)
    ```
    """

    def __init__(self) -> None:
        """Initialise l'assistant."""
        self.settings = get_settings()
        self.orchestrator: Orchestrator | None = None
        self.context: QAContext | None = None

    # ------------------------------------------------------------------
    # Méthodes de cycle de vie (Lifecycle helpers)
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AltioraQAAssistant:
        """Initialise l'orchestrateur lors de l'entrée dans le contexte asynchrone."""
        # Crée une instance de l'orchestrateur avec les dépendances nécessaires.
        self.orchestrator = Orchestrator(
            starcoder=None,  # À remplacer par une vraie implémentation si nécessaire
            redis_client=await get_redis_client(),
            config=self.settings,
            model_registry=None, # À remplacer par un vrai registre si nécessaire
        )
        await self.orchestrator.initialize()
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Ferme proprement l'orchestrateur lors de la sortie du contexte."""
        if self.orchestrator:
            await self.orchestrator.close()

    async def start_session(self, user_id: str, project_name: str = "default") -> QAContext:
        """Démarre une nouvelle session de QA.

        Args:
            user_id: L'identifiant de l'utilisateur.
            project_name: Le nom du projet associé à la session.

        Returns:
            Le contexte de la session nouvellement créée.
        """
        self.context = QAContext(
            user_id=user_id,
            project_name=project_name,
            session_id=f"{user_id}_{datetime.now():%Y%m%d_%H%M%S}",
            created_at=datetime.now(),
        )
        return self.context

    # ------------------------------------------------------------------
    # API Publique
    # ------------------------------------------------------------------

    async def run_full_pipeline(self, sfd_path: str) -> Dict[str, Any]:
        """Exécute le pipeline complet d'analyse de SFD et de génération de tests.

        C'est une méthode de commodité pour lancer tout le processus en un seul appel.

        Args:
            sfd_path: Le chemin vers le fichier de spécifications fonctionnelles (SFD).

        Returns:
            Un dictionnaire contenant les résultats du pipeline.

        Raises:
            RuntimeError: Si l'assistant n'a pas été initialisé via `async with`.
        """
        if self.orchestrator is None:
            raise RuntimeError("L'assistant n'est pas initialisé. Utilisez le gestionnaire de contexte `async with`.")
        request = SFDAnalysisRequest(content=Path(sfd_path).read_text())
        return await self.orchestrator.process_sfd_to_tests(request)

    def get_session_summary(self) -> Dict[str, Any]:
        """Retourne un résumé de la session en cours."""
        return {
            "session": asdict(self.context) if self.context else {},
            "status": "active" if self.context else "inactive",
        }


# ------------------------------------------------------------------
# Fabrique (Factory helper)
# ------------------------------------------------------------------

async def create_qa_assistant(
        user_id: str, project_name: str = "default"
) -> AltioraQAAssistant:
    """Fabrique pour créer et initialiser une instance de l'assistant.

    Args:
        user_id: L'identifiant de l'utilisateur.
        project_name: Le nom du projet.

    Returns:
        Une instance de `AltioraQAAssistant` prête à l'emploi.
    """
    assistant = AltioraQAAssistant()
    # Le `async with` garantit que __aenter__ et __aexit__ sont appelés.
    async with assistant:
        await assistant.start_session(user_id, project_name)
        return assistant