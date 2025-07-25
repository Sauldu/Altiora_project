# interaction_guardrail.py
"""
Real-time interaction gatekeeper for Altiora
- Runs every user message through **all** policy layers
- Returns masked text + verdict instantly
"""

import asyncio
from typing import Dict, Any
from .policy_enforcer import PolicyEnforcer
import logging

logger = logging.getLogger(__name__)


class InteractionGuardrail:
    """
    One-liner façade used **inside** every user-facing entry point:
    – chat
    – file upload
    – voice transcription
    – generated-test pipeline
    """

    def __init__(self):
        self.enforcer = PolicyEnforcer()

    async def check(
        self,
        user_id: str,
        raw_text: str,
        *,
        source: str = "chat",
        extra_meta: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Returns:
        {
            "allowed": bool,
            "masked_text": str,
            "violations": list[str],
            "audit_id": str,
        }
        """
        verdict = await self.enforcer.enforce(
            user_id=user_id,
            context=raw_text,
            workflow=source,
            extra_meta=extra_meta or {},
        )
        return {
            "allowed": verdict["allowed"],
            "masked_text": verdict["masked_context"],
            "violations": verdict["violations"],
            "audit_id": verdict["audit"]["timestamp"],  # quick ref
        }

    # ------------------------------------------------------------------
    # Fast synchronous wrapper for non-async code
    # ------------------------------------------------------------------
    def check_sync(self, user_id: str, raw_text: str, **kw) -> Dict[str, Any]:
        return asyncio.run(self.check(user_id, raw_text, **kw))


# ------------------------------------------------------------------
# Quick CLI test
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        gate = InteractionGuardrail()
        samples = [
            ("alice", "Salut, ça va ?"),
            ("bob", "Mon email est bob@mail.fr"),
            ("mallory", "T’es vraiment un naze"),
        ]
        for uid, txt in samples:
            res = await gate.check(uid, txt)
            logger.info(f"{uid}: {txt}")
            logger.info(f"→ allowed: {res['allowed']}")
            logger.info(f"→ masked: {res['masked_text']}")
            print("-" * 40)

    asyncio.run(demo())