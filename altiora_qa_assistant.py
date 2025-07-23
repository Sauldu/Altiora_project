# altiora_qa_assistant.py  (slim version)
from dataclasses import dataclass
from datetime import datetime

from src.orchestrator import Orchestrator


@dataclass
class QAContext:
    user_id: str
    project_name: str
    session_id: str
    created_at: datetime


class AltioraQAAssistant:
    """Lightweight façade for CLI / UI / API"""

    def __init__(self):
        self.orchestrator = Orchestrator()
        self.context: QAContext | None = None

    async def __aenter__(self):
        await self.orchestrator.initialize()
        return self

    async def __aexit__(self, *_):
        await self.orchestrator.close()

    async def start_session(self, user_id: str, project_name: str = "default"):
        self.context = QAContext(
            user_id=user_id,
            project_name=project_name,
            session_id=f"{user_id}_{datetime.now():%Y%m%d_%H%M%S}",
            created_at=datetime.now(),
        )
        return self.context

    async def run_full_pipeline(self, sfd_path: str):
        """One-liner for CLI / Streamlit"""
        return await self.orchestrator.process_sfd_to_tests(sfd_path)
