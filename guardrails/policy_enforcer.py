"""
policy_enforcer.py
Orchestrates all business & compliance rules before any data is stored or returned.
Order of enforcement:
1. Toxicity check (French lexicon)  → block or mask
2. PII & privacy check              → mask + retention rules
3. Business rules                   → validate workflow objects
4. Final verdict (allow / block / log)
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

# Policy engines
from .toxicity_guardrail import ToxicityGuardrail
from policies.privacy_policy import PrivacyPolicy
from policies.business_rules import BusinessRules  # see next file

# Logging
import logging
logger = logging.getLogger(__name__)


class PolicyEnforcer:
    """
    Single entry-point for rule enforcement:
    - Every user message
    - Every generated test
    - Every ALM/Excel export
    """

    def __init__(self):
        self.toxicity = ToxicityGuardrail()
        self.privacy  = PrivacyPolicy()
        self.business = BusinessRules()

    # ------------------------------------------------------------------
    # Public façade
    # ------------------------------------------------------------------
    async def enforce(
        self,
        *,
        user_id: str,
        context: str,          # raw text or object
        workflow: str = "chat",  # chat | test | export
        extra_meta: Dict = None,
    ) -> Dict[str, Any]:
        """
        Returns:
        {
            "allowed": bool,
            "masked_context": str,
            "violations": List[str],
            "retention_seconds": int,
            "audit": {...}
        }
        """
        extra_meta = extra_meta or {}
        violations: List[str] = []
        masked_context = context
        retention = 0

        # 1. Toxicity
        tox_verdict = await self.toxicity.evaluate(user_id, str(context))
        if not tox_verdict["allowed"]:
            violations.extend(tox_verdict["reason"].split("; "))
            return self._reject(violations, tox_verdict)

        # 2. Privacy
        priv_report = self.privacy.scan_and_mask(str(context))
        masked_context = priv_report.text
        retention = priv_report.retention_seconds
        if not priv_report.can_store:
            violations.append("PII storage forbidden")

        # 3. Business rules
        biz_verdict = await self.business.validate(
            masked_context, workflow=workflow, meta=extra_meta
        )
        if not biz_verdict["ok"]:
            violations.extend(biz_verdict["violations"])

        # 4. Final decision
        allowed = len(violations) == 0
        audit_log = {
            "user_id": user_id,
            "workflow": workflow,
            "timestamp": datetime.utcnow().isoformat(),
            "allowed": allowed,
            "violations": violations,
            "retention_seconds": retention,
            "original_length": len(str(context)),
            "masked_length": len(masked_context),
        }
        self._append_audit(audit_log)

        return {
            "allowed": allowed,
            "masked_context": masked_context,
            "violations": violations,
            "retention_seconds": retention,
            "audit": audit_log,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _reject(self, violations: List[str], tox_v: Dict) -> Dict[str, Any]:
        return {
            "allowed": False,
            "masked_context": tox_v.get("masked_text", ""),
            "violations": violations,
            "retention_seconds": 0,
            "audit": {"rejected": True, "violations": violations},
        }

    def _append_audit(self, entry: Dict[str, Any}):
        try:
            audit_file = Path("logs/policy_audit.jsonl")
            audit_file.parent.mkdir(exist_ok=True)
            with audit_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except (IOError, OSError) as e:
            logger.error(f"Error writing to audit log: {e}")


# ------------------------------------------------------------------
# Quick CLI demo
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    async def demo():
        enforcer = PolicyEnforcer()
        cases = [
            {"user_id": "alice", "context": "Salut, tu vas bien ?", "workflow": "chat"},
            {"user_id": "bob", "context": "Mon email est bob@mail.fr", "workflow": "test"},
            {"user_id": "mallory", "context": "T’es un gros c*n", "workflow": "chat"},
        ]
        for c in cases:
            verdict = await enforcer.enforce(**c)
            print("-" * 60)
            print("Case:", c["context"])
            print("→ allowed:", verdict["allowed"])
            print("→ violations:", verdict["violations"])

    asyncio.run(demo())
