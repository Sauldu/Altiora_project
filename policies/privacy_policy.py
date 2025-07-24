# privacy_policy.py
"""
Privacy policy engine for Altiora – French-user centric
- Detects and redacts French PII (email, téléphone, carte bancaire, etc.)
- GDPR-compliant retention rules
- User consent & data subject rights helpers
"""

import re
import json
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------
@dataclass
class PIIDetection:
    type: str            # email, phone, credit_card, etc.
    value: str           # original token
    redacted: str        # masked token
    start: int           # char offset
    end: int


@dataclass
class PrivacyReport:
    text: str
    pii_list: List[PIIDetection]
    retention_seconds: int
    can_store: bool
    user_consent_required: bool


# ------------------------------------------------------------------
# Regex patterns for French PII
# ------------------------------------------------------------------
PII_PATTERNS = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone": r"(\+?33[-.\s]?|0)[1-9]([-.\s]?\d{2}){4}",
    "credit_card": r"\b(?:\d{4}[\s-]?){3}\d{4}\b",
    "social_security": r"\b\d{3}[\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{3}\b",
    "passport": r"\b[A-Z]{1,2}\d{6,9}\b",
    "driver_license": r"\b\d{2}[\s-]?\d{2}[\s-]?\d{2}[\s-]?\d{5}[\s-]?\d{2}\b",
    "postal_code": r"\b\d{5}\b",
    "iban": r"\bFR\d{2}\s?(\d{4}\s?){4}\d{2}\b",
}


# ------------------------------------------------------------------
# GDPR retention rules (seconds)
# ------------------------------------------------------------------
RETENTION_RULES = {
    "email": 30 * 24 * 3600,          # 30 j
    "phone": 7 * 24 * 3600,           # 7 j
    "credit_card": 0,                 # never store raw
    "social_security": 0,             # never store
    "passport": 0,                    # never store
    "driver_license": 0,              # never store
    "postal_code": 365 * 24 * 3600,   # 1 an
    "iban": 90 * 24 * 3600,           # 90 j
}


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
class PrivacyPolicy:

    def __init__(self, config_path: Optional[Path] = None):
        self.config = self._load_config(config_path)
        self.consent_db = ConsentDB(config_path)

    # ------------------------------------------------------------------
    # PII detection & masking
    # ------------------------------------------------------------------
    def scan_and_mask(self, text: str, *, mask_char: str = "*") -> PrivacyReport:
        """Detect PII, mask it, and return report."""
        pii_list = []
        for pii_type, pattern in PII_PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                original = match.group(0)
                redacted = self._mask(original, mask_char)
                pii_list.append(
                    PIIDetection(
                        type=pii_type,
                        value=original,
                        redacted=redacted,
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # Build masked text
        masked_text = text
        for det in sorted(pii_list, key=lambda d: d.start, reverse=True):
            masked_text = (
                masked_text[: det.start] + det.redacted + masked_text[det.end :]
            )

        # Determine retention
        max_retention = max(
            (RETENTION_RULES.get(p.type, 0) for p in pii_list), default=0
        )
        can_store = max_retention > 0
        user_consent_required = any(p.type in {"email", "phone"} for p in pii_list)

        return PrivacyReport(
            text=masked_text,
            pii_list=pii_list,
            retention_seconds=max_retention,
            can_store=can_store,
            user_consent_required=user_consent_required,
        )

    # ------------------------------------------------------------------
    # Consent helpers
    # ------------------------------------------------------------------
    def record_consent(
        self, user_id: str, pii_types: List[str], granted: bool, expiry_days: int = 365
    ):
        """Store user consent choice."""
        self.consent_db.add(
            user_id=user_id,
            pii_types=pii_types,
            granted=granted,
            expires_at=datetime.utcnow() + timedelta(days=expiry_days),
        )

    def has_consent(self, user_id: str, pii_type: str) -> bool:
        """Check if user has valid consent for storing PII."""
        return self.consent_db.is_valid(user_id, pii_type)

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------
    def log_access(self, user_id: str, pii_type: str, action: str):
        """Log any PII access for GDPR audit."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "pii_type": pii_type,
            "action": action,
        }
        self._append_audit_log(log_entry)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def _mask(self, value: str, mask_char: str) -> str:
        """Mask value keeping first & last 2 chars."""
        if len(value) <= 4:
            return mask_char * len(value)
        return value[:2] + mask_char * (len(value) - 4) + value[-2:]

    def _load_config(self, path: Optional[Path]) -> Dict:
        """Load custom retention config if provided."""
        if path and path.exists():
            return json.loads(path.read_text())
        return RETENTION_RULES

    def _append_audit_log(self, entry: Dict):
        """Append to GDPR audit file."""
        try:
            audit_file = Path("logs/privacy_audit.jsonl")
            audit_file.parent.mkdir(exist_ok=True)
            with audit_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except (IOError, OSError) as e:
            logger.error(f"Error writing to audit log: {e}")


# ------------------------------------------------------------------
# Consent persistence (simple JSONL)
# ------------------------------------------------------------------
class ConsentDB:
    def __init__(self, config_path: Optional[Path]):
        self.file = Path(config_path or "data/consent.jsonl")

    def add(
        self,
        user_id: str,
        pii_types: List[str],
        granted: bool,
        expires_at: datetime,
    ):
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "user_id": user_id,
                "pii_types": pii_types,
                "granted": granted,
                "expires_at": expires_at.isoformat(),
                "created_at": datetime.utcnow().isoformat(),
            }
            with self.file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except (IOError, OSError) as e:
            logger.error(f"Error writing to consent database: {e}")

    def is_valid(self, user_id: str, pii_type: str) -> bool:
        """Check if latest consent for this (user, pii_type) is granted & not expired."""
        now = datetime.utcnow()
        try:
            with self.file.open("r", encoding="utf-8") as f:
                for line in reversed(list(f)):
                    record = json.loads(line)
                    if (
                        record["user_id"] == user_id
                        and pii_type in record["pii_types"]
                    ):
                        if datetime.fromisoformat(record["expires_at"]) < now:
                            return False
                        return record["granted"]
        except FileNotFoundError:
            pass
        return False


# ------------------------------------------------------------------
# CLI demo
# ------------------------------------------------------------------
if __name__ == "__main__":
    policy = PrivacyPolicy()

    sample = (
        "Contactez-moi à jean.dupont@mail.fr ou au 06.12.34.56.78, "
        "ma carte est 4532-1234-5678-9012."
    )
    report = policy.scan_and_mask(sample)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))