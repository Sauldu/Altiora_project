# toxicity_guardrail.py
"""
Real-time toxicity & PII guardrail wrapper for Altiora
– plugs into every user interaction and enforces the privacy/toxicity policy
"""

import asyncio
import json
from typing import Dict, Any
from policies.toxicity_policy import ToxicityPolicy, DetectionResult
from policies.privacy_policy import PrivacyPolicy, PrivacyReport
import logging

logger = logging.getLogger(__name__)


class ToxicityGuardrail:
    """
    High-level guardrail:
    1. Detects toxic content (French lexicon)
    2. Detects / masks French PII
    3. Logs & optionally blocks the interaction
    """

    def __init__(self):
        self.toxicity = ToxicityPolicy(use_external=False)   # regex only by default
        self.privacy  = PrivacyPolicy()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def evaluate(self, user_id: str, text: str) -> Dict[str, Any]:
        """
        Return a verdict dict:
        {
            "allowed": bool,
            "masked_text": str,
            "reason": str,
            "details": { … }
        }
        """
        # 1. Toxicity scan
        tox: DetectionResult = await self.toxicity.scan(text)

        # 2. Privacy scan
        priv: PrivacyReport = self.privacy.scan_and_mask(text)

        # 3. Decision logic
        blocked = tox.severity.value >= 3 or not priv.can_store
        reason  = self._build_reason(tox, priv)

        # 4. Audit log
        self._log_decision(user_id, tox, priv, blocked)

        return {
            "allowed": not blocked,
            "masked_text": priv.text,
            "reason": reason,
            "details": {
                "toxicity": tox,
                "privacy": priv,
            },
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_reason(self, tox: DetectionResult, priv: PrivacyReport) -> str:
        msgs = []
        if tox.toxic:
            msgs.append(f"toxic content ({', '.join(tox.categories)})")
        if not priv.can_store:
            msgs.append("PII retention forbidden")
        return "; ".join(msgs) or "clean"

    def _log_decision(self, user_id: str, tox: DetectionResult, priv: PrivacyReport, blocked: bool):
        entry = {
            "user_id": user_id,
            "blocked": blocked,
            "toxicity_categories": tox.categories,
            "pii_types": [p.type for p in priv.pii_list],
            "timestamp": asyncio.get_event_loop().time(),
        }
        logger.info(json.dumps(entry, ensure_ascii=False))


# ------------------------------------------------------------------
# Quick CLI demo
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        guard = ToxicityGuardrail()
        samples = [
            "Bonjour, ça va ?",
            "T’es vraiment un naze, va te faire voir.",
        ]
        for s in samples:
            verdict = await guard.evaluate("demo_user", s)
            print("-" * 50)
            print("Original :", s)
            print("Verdict  :", verdict)

    asyncio.run(demo())