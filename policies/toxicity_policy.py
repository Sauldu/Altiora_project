# policies/toxicity_policy.py
"""Politique de détection de toxicité et de PII pour Altiora.

Ce module combine une analyse rapide basée sur des expressions régulières locales
(avec un lexique français) et des appels optionnels à des API externes pour une
analyse plus approfondie. Il fournit un score de sévérité et masque les PII.
"""

import re
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

# Importation de PrivacyPolicy pour la détection de PII
from .privacy_policy import PrivacyPolicy, PrivacyReport

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Niveaux de sévérité pour le contenu détecté."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class DetectionResult:
    """Résultat d'une analyse de toxicité."""
    toxic: bool
    severity: Severity
    categories: List[str]
    pii_found: List[str]
    confidence: float
    provider: str


# ------------------------------------------------------------------
# Lexique et expressions régulières (Français)
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
    """Analyse le texte pour la toxicité et les PII."""

    def __init__(
        self,
        *,
        use_external: bool = False,
        openai_key: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
    ):
        """Initialise la politique.

        Args:
            use_external: Si True, utilise les API externes (OpenAI, Azure) comme fallback.
            openai_key: Clé API pour OpenAI Moderation.
            azure_endpoint: Endpoint pour Azure Content Safety.
        """
        self.use_external = use_external and httpx is not None
        self.openai_key = openai_key
        self.azure_endpoint = azure_endpoint

    # ------------------------------------------------------------------
    # API Publique
    # ------------------------------------------------------------------
    async def scan(self, text: str) -> DetectionResult:
        """Analyse un texte (français) pour la toxicité et les PII.

        La stratégie est d'abord locale (rapide) puis externe (plus lente mais potentiellement
        plus précise). Si une toxicité élevée est détectée localement, le résultat est
        retourné immédiatement.
        """
        text_lower = text.lower()
        regex_result = self._regex_scan(text_lower)

        # Si la sévérité est déjà haute, on retourne le résultat immédiatement.
        if regex_result.severity in (Severity.HIGH, Severity.CRITICAL):
            return regex_result

        # Si l'option est activée, on utilise une API externe comme fallback.
        if self.use_external:
            external_result = await self._external_scan(text_lower)
            # On retourne le résultat externe seulement s'il est plus sévère.
            if external_result.severity.value > regex_result.severity.value:
                return external_result

        return regex_result

    # ------------------------------------------------------------------
    # Implémentation par expressions régulières
    # ------------------------------------------------------------------
    def _regex_scan(self, text: str) -> DetectionResult:
        """Analyse le texte en utilisant les expressions régulières locales."""
        toxic = False
        categories: List[str] = []
        max_sev = Severity.LOW
        pii_tokens: List[str] = []

        # Détection de la toxicité
        for cat, patterns in TOXIC_REGEXES.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    toxic = True
                    if cat not in categories:
                        categories.append(cat)
                    max_sev = max(max_sev, self._severity_from_cat(cat))

        # Détection des PII
        for pii_type, pattern in PII_REGEXES.items():
            for match in re.finditer(pattern, text):
                pii_tokens.append(match.group(0))

        return DetectionResult(
            toxic=toxic,
            severity=max_sev,
            categories=categories,
            pii_found=pii_tokens,
            confidence=0.9,  # Confiance élevée pour les regex car déterministes
            provider="regex",
        )

    # ------------------------------------------------------------------
    # Assistants pour les API externes
    # ------------------------------------------------------------------
    async def _external_scan(self, text: str) -> DetectionResult:
        """Tente d'analyser le texte avec une API externe."""
        if self.openai_key:
            return await self._openai_moderation(text)
        if self.azure_endpoint:
            return await self._azure_content_safety(text)
        return self._fallback_result()

    async def _openai_moderation(self, text: str) -> DetectionResult:
        """Analyse le texte avec l'API de modération d'OpenAI."""
        url = "https://api.openai.com/v1/moderations"
        headers = {"Authorization": f"Bearer {self.openai_key}"}
        payload = {"input": text}

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status() # Lève une exception pour les codes 4xx/5xx
            except httpx.HTTPStatusError as e:
                logger.error(f"Erreur de l'API de modération OpenAI : {e.response.text}")
                return self._fallback_result()

        data = resp.json()
        result = data["results"][0]
        categories = result["categories"]
        scores = result["category_scores"]

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
        """Analyse le texte avec l'API Azure Content Safety."""
        url = f"{self.azure_endpoint}/contentsafety/text:analyze?api-version=2023-10-01"
        headers = {"Content-Type": "application/json"}
        payload = {"text": text, "categories": ["Hate", "Sexual", "Violence", "SelfHarm"]}

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f"Erreur de l'API Azure Content Safety : {e.response.text}")
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
            confidence=0.8, # Confiance arbitraire pour Azure
            provider="azure",
        )

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------
    def _severity_from_cat(self, category: str) -> Severity:
        """Mappe une catégorie de regex à un niveau de sévérité."""
        mapping = {
            "hate": Severity.HIGH,
            "harassment": Severity.MEDIUM,
            "sexual": Severity.MEDIUM,
            "violence": Severity.HIGH,
        }
        return mapping.get(category, Severity.LOW)

    def _severity_from_openai_cat(self, category: str) -> Severity:
        """Mappe une catégorie de l'API OpenAI à un niveau de sévérité."""
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
        """Retourne un résultat non toxique en cas d'échec des API externes."""
        return DetectionResult(
            toxic=False,
            severity=Severity.LOW,
            categories=[],
            pii_found=[],
            confidence=0.0,
            provider="none",
        )


# ------------------------------------------------------------------
# Démonstration en ligne de commande
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
            logging.info(f"{s} → {res}")

    asyncio.run(demo())
