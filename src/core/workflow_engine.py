# src/core/workflow_engine.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

from post_processing.excel_formatter import ExcelFormatter  # noqa: F401
from src.core.state_manager import get_state_manager
from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from src.models.starcoder2.starcoder2_interface import (
    PlaywrightTestConfig,
    StarCoder2OllamaInterface,
    TestType,
)

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """End-to-end QA workflow orchestrator with progress tracking."""

    def __init__(self) -> None:
        self.qwen3: Optional[Qwen3OllamaInterface] = None
        self.starcoder2: Optional[StarCoder2OllamaInterface] = None
        self.excel_formatter = ExcelFormatter()
        self.state = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def initialize(self) -> None:
        self.qwen3 = Qwen3OllamaInterface()
        await self.qwen3.initialize()

        self.starcoder2 = StarCoder2OllamaInterface()
        await self.starcoder2.initialize()

        self.state = await get_state_manager()

    async def close(self) -> None:
        if self.qwen3:
            await self.qwen3.close()
        if self.starcoder2:
            await self.starcoder2.close()

    # ------------------------------------------------------------------
    # Main workflow
    # ------------------------------------------------------------------
    async def run_sfd_to_test_suite(self, sfd_path: str, session_id: str) -> Dict[str, Any]:
        steps = [
            ("load_sfd", lambda: self._load_sfd(sfd_path)),
            ("analyze_sfd", lambda data: self._analyze_sfd(data["content"])),
            ("generate_tests", lambda data: self._generate_tests(data["scenarios"])),
            ("export_report", lambda data: self._export_report(data["tests"])),
        ]

        context: Dict[str, Any] = {}
        for step_name, step_func in steps:
            await self.state.set_pipeline_progress(session_id, step_name, 0.0)
            try:
                result = await asyncio.wait_for(step_func(context), timeout=300)
                context.update(result)
                await self.state.set_pipeline_progress(session_id, step_name, 1.0)
            except Exception as e:
                logger.error("Step '%s' failed: %s", step_name, e)
                await self.state.set_pipeline_progress(session_id, step_name, -1.0)
                raise RuntimeError(f"Workflow step '{step_name}' failed") from e

        return {
            "session_id": session_id,
            "workflow_status": "completed",
            "final_report": context.get("report_path"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Private steps
    # ------------------------------------------------------------------
    @staticmethod
    async def _load_sfd(path: str) -> Dict[str, Any]:
        sfd_file = Path(path).resolve()
        if not sfd_file.exists():
            raise FileNotFoundError(sfd_file)

        async with aiofiles.open(sfd_file, encoding="utf-8") as f:
            content = await f.read()
        return {"content": content, "file_size": sfd_file.stat().st_size}

    async def _analyze_sfd(self, content: str) -> Dict[str, Any]:
        result = await self.qwen3.analyze_sfd(content, extraction_type="complete")
        return {"scenarios": result.get("scenarios", [])}

    async def _generate_tests(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        generated: List[Dict[str, Any]] = []
        config = PlaywrightTestConfig(browser="chromium", use_page_object=False)
        for scenario in scenarios:
            code = await self.starcoder2.generate_playwright_test(
                scenario=scenario, config=config, test_type=TestType.E2E
            )
            generated.append({"scenario": scenario, "test": code})
        return {"tests": generated}

    async def _export_report(self, tests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate Excel matrix and return path."""
        # Ensure ExcelFormatter has create_test_matrix implemented
        # If stub is used, replace with real implementation or raise NotImplementedError
        report_path = await self.excel_formatter.create_test_matrix(
            scenarios=[t["scenario"] for t in tests],
            tests=[t["test"] for t in tests],
        )
        return {"report_path": str(report_path)}

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    async def get_progress(self, session_id: str) -> Dict[str, Any]:
        return await self.state.get_pipeline_progress(session_id)
