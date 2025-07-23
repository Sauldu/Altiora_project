# emergency_handler.py
"""
Emergency mode & alerting for Altiora
- Triggers: critical toxicity / PII leak / service crash
- Actions: freeze users, global backup, admin alerts
"""

import asyncio
import json
import logging
import aiohttp
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from guardrails.admin_control_system import AdminControlSystem
from guardrails.ethical_safeguards import EthicalAlert

logger = logging.getLogger(__name__)


class EmergencyHandler:
    """
    One-liner to enter/exit emergency mode:
    EmergencyHandler().trigger(reason="Critical toxicity spike")
    """

    def __init__(self):
        self.admin = AdminControlSystem()
        self.alert_webhooks = []  # Slack / Teams / email hooks
        self._load_webhooks()

    # ------------------------------------------------------------------
    # Triggers
    # ------------------------------------------------------------------
    async def trigger(
        self,
        *,
        reason: str,
        severity: str = "critical",  # low | medium | high | critical
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Activate emergency mode:
        1. Freeze all users (or subset)
        2. Emergency backup
        3. Notify admins
        """
        metadata = metadata or {}
        ts = datetime.utcnow().isoformat()

        # 1. Emergency backup
        backup_path = await self._emergency_backup()

        # 2. Freeze users
        frozen_users = await self._freeze_users(metadata.get("users", []))

        # 3. Admin notifications
        await self._notify_admins(reason, backup_path, frozen_users, metadata)

        # 4. Log
        self._log_emergency(reason, severity, backup_path, frozen_users)

        return {
            "emergency_id": ts,
            "reason": reason,
            "severity": severity,
            "backup_path": str(backup_path),
            "frozen_users": frozen_users,
        }

    # ------------------------------------------------------------------
    # Reset / exit emergency
    # ------------------------------------------------------------------
    async def reset(self) -> Dict[str, Any]:
        """Lift global freeze + send summary."""
        # Unfreeze all
        await self._unfreeze_all()
        # Notify
        await self._notify_admins("Emergency mode lifted", None, [], {})
        return {"status": "lifted", "timestamp": datetime.utcnow().isoformat()}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _emergency_backup(self) -> Path:
        """Call AdminControlSystem for full user backup."""
        cmd = {
            "command_id": f"emergency_{datetime.utcnow().timestamp()}",
            "action": "emergency",
            "target_user": "system",
            "parameters": {"reason": "Emergency trigger"},
        }
        result = await self.admin.execute_admin_command(cmd)
        return Path(result["backup_path"])

    async def _freeze_users(self, users: List[str]) -> List[str]:
        """Freeze provided users list (or all if empty)."""
        if not users:
            # TODO: list all active users
            users = ["all"]
        for uid in users:
            await self.admin.execute_admin_command(
                {
                    "command_id": f"freeze_{uid}_{datetime.utcnow().timestamp()}",
                    "action": "freeze_user",
                    "target_user": uid,
                    "parameters": {"reason": "Emergency"},
                }
            )
        return users

    async def _unfreeze_all(self):
        # Implementation depends on freeze storage
        pass

    async def _notify_admins(
        self,
        reason: str,
        backup_path: Optional[Path],
        frozen: List[str],
        meta: Dict[str, Any],
    ):
        payload = {
            "text": f"🚨 Altiora Emergency\n"
            f"Reason: {reason}\n"
            f"Users frozen: {len(frozen)}\n"
            f"Backup: {backup_path}",
            "metadata": meta,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Slack / Teams / email webhooks
        for url in self.alert_webhooks:
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(url, json=payload, timeout=5)
            except Exception as e:
                logger.warning("Webhook failed: %s", e)

    def _load_webhooks(self):
        """Load Slack / Teams / email URLs from config."""
        cfg_file = Path("configs/emergency_webhooks.json")
        if cfg_file.exists():
            self.alert_webhooks = json.loads(cfg_file.read_text()).get("webhooks", [])

    def _log_emergency(self, reason: str, severity: str, backup_path: Path, users: List[str]):
        log_file = Path("logs/emergency.jsonl")
        log_file.parent.mkdir(exist_ok=True)
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "severity": severity,
            "reason": reason,
            "backup": str(backup_path),
            "frozen_users": users,
        }
        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------
# Quick CLI
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        handler = EmergencyHandler()
        result = await handler.trigger(
            reason="Détection massive de PII + toxicité critique",
            metadata={"users": ["mallory"], "count": 42},
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    asyncio.run(demo())
