# toxicity_policy.py
"""
Toxicity & PII detection policy for Altiora – English code, French lexicon
- Fast in-process regex rules (French vocabulary)
- Optional external API fallbacks
- PII redaction + severity scoring
"""

import re
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

# Importation de PrivacyPolicy
from .privacy_policy import PrivacyPolicy, PrivacyReport

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)


class Severity(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class DetectionResult:
    toxic: bool
    severity: Severity
    categories: List[str]
    pii_found: List[str]
    confidence: float
    provider: str


# ------------------------------------------------------------------
# French keywords & regex
# ------------------------------------------------------------------
TOXIC_REGEXES = {
    "hate": [
        r"\b(nazi|facho|raciste|suprémaciste)\b",
        r"\b(tuer\s+(tous?|les?)|pendre\s+les?|gazer\s+les?)\b",
    ],
    "harassment": [
        r"\b(naze|con|idiot|imbécile|débile|pd|tapette)\b",
        r"\b(ferme\s+ta\s+gueule|dégage|va\s+te\s+faire)\b",
    ],
    "sexual": [
        r"\b(porno?|xxx|nud?e?|viol|agression\s+sexuelle)\b",
    ],
    "violence": [
        r"\b(bombe|tuer|tue|tirer|poignarder|massacrer)\b",
    ],
}

PII_REGEXES = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone": r"(\+?33[-.\s]?|0)[1-9]([-.\s]?\d{2}){4}",
    "credit_card": r"\b(?:\d{4}[\s-]?){3}\d{4}\b",
    "social_security": r"\b\d{3}[\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{3}\b",
}


class ToxicityPolicy:

    def __init__(
        self,
        *,
        use_external: bool = False,
        openai_key: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
    ):
        self.use_external = use_external and httpx is not None
        self.openai_key = openai_key
        self.azure_endpoint = azure_endpoint

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def scan(self, text: str) -> DetectionResult:
        """Scan text (French) for toxicity & PII."""
        text_lower = text.lower()
        regex_result = self._regex_scan(text_lower)
        if regex_result.severity in (Severity.HIGH, Severity.CRITICAL):
            return regex_result

        if self.use_external:
            external = await self._external_scan(text_lower)
            if external.severity.value > regex_result.severity.value:
                return external

        return regex_result

    # ------------------------------------------------------------------
    # Regex implementation
    # ------------------------------------------------------------------
    def _regex_scan(self, text: str) -> DetectionResult:
        toxic = False
        categories: List[str] = []
        max_sev = Severity.LOW
        pii_tokens: List[str] = []

        # Toxicity
        for cat, patterns in TOXIC_REGEXES.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    toxic = True
                    if cat not in categories:
                        categories.append(cat)
                    max_sev = max(max_sev, self._severity_from_cat(cat))

        # PII
        for pii_type, pattern in PII_REGEXES.items():
            for match in re.finditer(pattern, text):
                pii_tokens.append(match.group(0))

        return DetectionResult(
            toxic=toxic,
            severity=max_sev,
            categories=categories,
            pii_found=pii_tokens,
            confidence=0.9,
            provider="regex",
        )

    # ------------------------------------------------------------------
    # External API helpers
    # ------------------------------------------------------------------
    async def _external_scan(self, text: str) -> DetectionResult:
        if self.openai_key:
            return await self._openai_moderation(text)
        if self.azure_endpoint:
            return await self._azure_content_safety(text)
        return self._fallback_result()

    async def _openai_moderation(self, text: str) -> DetectionResult:
        url = "https://api.openai.com/v1/moderations"
        headers = {"Authorization": f"Bearer {self.openai_key}"}
        payload = {"input": text}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error("OpenAI moderation error: %s", resp.text)
                return self._fallback_result()

        data = resp.json()
        categories = data["results"][0]["categories"]
        scores = data["results"][0]["category_scores"]

        toxic = any(categories.values())
        max_sev = max(
            (self._severity_from_openai_cat(name) for name, flag in categories.items() if flag),
            default=Severity.LOW,
        )
        return DetectionResult(
            toxic=toxic,
            severity=max_sev,
            categories=[k for k, v in categories.items() if v],
            pii_found=[],
            confidence=max(scores.values()),
            provider="openai",
        )

    async def _azure_content_safety(self, text: str) -> DetectionResult:
        url = f"{self.azure_endpoint}/contentsafety/text:analyze?api-version=2023-10-01"
        headers = {"Content-Type": "application/json"}
        payload = {"text": text, "categories": ["Hate", "Sexual", "Violence", "SelfHarm"]}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error("Azure Content Safety error: %s", resp.text)
                return self._fallback_result()

        data = resp.json()
        toxic = any(block["severity"] > 0 for block in data.get("categoriesAnalysis", []))
        max_sev = max(
            (Severity(block["severity"]) for block in data["categoriesAnalysis"] if block["severity"] > 0),
            default=Severity.LOW,
        )
        return DetectionResult(
            toxic=toxic,
            severity=max_sev,
            categories=[b["category"] for b in data["categoriesAnalysis"] if b["severity"] > 0],
            pii_found=[],
            confidence=0.8,
            provider="azure",
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def _severity_from_cat(self, category: str) -> Severity:
        mapping = {
            "hate": Severity.HIGH,
            "harassment": Severity.MEDIUM,
            "sexual": Severity.MEDIUM,
            "violence": Severity.HIGH,
        }
        return mapping.get(category, Severity.LOW)

    def _severity_from_openai_cat(self, category: str) -> Severity:
        return {
            "hate": Severity.HIGH,
            "hate/threatening": Severity.CRITICAL,
            "harassment": Severity.MEDIUM,
            "harassment/threatening": Severity.HIGH,
            "sexual": Severity.MEDIUM,
            "sexual/minors": Severity.CRITICAL,
            "violence": Severity.HIGH,
            "violence/graphic": Severity.CRITICAL,
            "self-harm": Severity.CRITICAL,
        }.get(category, Severity.LOW)

    def _fallback_result(self) -> DetectionResult:
        return DetectionResult(
            toxic=False,
            severity=Severity.LOW,
            categories=[],
            pii_found=[],
            confidence=0.0,
            provider="none",
        )


# ------------------------------------------------------------------
# CLI demo
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    async def demo():
        policy = ToxicityPolicy(use_external=False)
        samples = [
            "Bonjour, comment vas-tu ?",
            "T’es vraiment un gros débile, ferme-la !",
            "Mon email est pierre.dupont@mail.fr et ma carte 1234-5678-9012-3456",
        ]
        for s in samples:
            res = await policy.scan(s)
            print(f"{s} → {res}")

    asyncio.run(demo())