# src/core/altiora_qa_assistant.py
"""
Altiora QA Assistant – ultra-light façade
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from src.config.settings import get_settings

from src.infrastructure.redis_config import get_redis_client
from src.models.sfd_models import SFDAnalysisRequest
from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Session context
# ------------------------------------------------------------------

@dataclass
class QAContext:
    user_id: str
    project_name: str
    session_id: str
    created_at: datetime


class AltioraQAAssistant:
    """Lightweight façade for CLI / UI / API"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.orchestrator: Orchestrator | None = None
        self.context: QAContext | None = None

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AltioraQAAssistant:
        self.orchestrator = Orchestrator(
            starcoder=None,
            redis_client=await get_redis_client(),
            config=self.settings,
            model_registry=None,
        )
        await self.orchestrator.initialize()
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self.orchestrator:
            await self.orchestrator.close()

    async def start_session(self, user_id: str, project_name: str = "default") -> QAContext:
        self.context = QAContext(
            user_id=user_id,
            project_name=project_name,
            session_id=f"{user_id}_{datetime.now():%Y%m%d_%H%M%S}",
            created_at=datetime.now(),
        )
        return self.context

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_full_pipeline(self, sfd_path: str) -> Dict[str, Any]:
        """One-liner for CLI / Streamlit / FastAPI"""
        if self.orchestrator is None:
            raise RuntimeError("Assistant not initialised – use async context manager")
        request = SFDAnalysisRequest(content=Path(sfd_path).read_text())
        return await self.orchestrator.process_sfd_to_tests(request)

    def get_session_summary(self) -> Dict[str, Any]:
        return {
            "session": asdict(self.context) if self.context else {},
            "status": "active" if self.context else "inactive",
        }


# ------------------------------------------------------------------
# Factory helper (module level)
# ------------------------------------------------------------------

async def create_qa_assistant(
        user_id: str, project_name: str = "default"
) -> AltioraQAAssistant:
    """Convenience factory"""
    assistant = AltioraQAAssistant()
    async with assistant:
        await assistant.start_session(user_id, project_name)
        return assistant
