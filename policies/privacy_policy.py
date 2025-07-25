# policies/privacy_policy.py
"""Moteur de politique de confidentialité pour Altiora, centré sur l'utilisateur français.

Ce module fournit des fonctionnalités essentielles pour la conformité RGPD :
- Détection et masquage d'informations personnelles identifiables (PII) françaises.
- Application de règles de rétention des données.
- Gestion du consentement de l'utilisateur et journalisation pour l'audit.
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
# Structures de données
# ------------------------------------------------------------------
@dataclass
class PIIDetection:
    """Représente une information personnelle identifiable (PII) détectée."""
    type: str       # Type de PII (ex: email, phone).
    value: str      # La valeur originale détectée.
    redacted: str   # La valeur masquée.
    start: int      # L'index de début dans le texte original.
    end: int        # L'index de fin.

@dataclass
class PrivacyReport:
    """Rapport généré après l'analyse d'un texte."""
    text: str
    pii_list: List[PIIDetection]
    retention_seconds: int
    can_store: bool
    user_consent_required: bool


# ------------------------------------------------------------------
# Constantes de la politique
# ------------------------------------------------------------------

# Expressions régulières pour détecter les PII courantes en France.
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

# Règles de rétention des données en secondes, conformément au RGPD.
# Une valeur de 0 signifie que la donnée ne doit jamais être stockée.
RETENTION_RULES = {
    "email": 30 * 24 * 3600,          # 30 jours
    "phone": 7 * 24 * 3600,           # 7 jours
    "credit_card": 0,                 # Ne jamais stocker
    "social_security": 0,             # Ne jamais stocker
    "passport": 0,                    # Ne jamais stocker
    "driver_license": 0,              # Ne jamais stocker
    "postal_code": 365 * 24 * 3600,   # 1 an
    "iban": 90 * 24 * 3600,           # 90 jours
}


# ------------------------------------------------------------------
# API Publique
# ------------------------------------------------------------------
class PrivacyPolicy:
    """Classe principale pour la gestion de la politique de confidentialité."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialise la politique, en chargeant une configuration personnalisée si fournie."""
        self.config = self._load_config(config_path)
        self.consent_db = ConsentDB(config_path)

    # ------------------------------------------------------------------
    # Détection et masquage de PII
    # ------------------------------------------------------------------
    def scan_and_mask(self, text: str, *, mask_char: str = "*") -> PrivacyReport:
        """Analyse un texte, masque les PII et retourne un rapport détaillé."""
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

        # Construit le texte masqué en remplaçant les PII détectées.
        masked_text = text
        for det in sorted(pii_list, key=lambda d: d.start, reverse=True):
            masked_text = (
                masked_text[: det.start] + det.redacted + masked_text[det.end :]
            )

        # Détermine la durée de rétention maximale et si le consentement est requis.
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
    # Gestion du consentement
    # ------------------------------------------------------------------
    def record_consent(
        self, user_id: str, pii_types: List[str], granted: bool, expiry_days: int = 365
    ):
        """Enregistre le choix de consentement d'un utilisateur."""
        self.consent_db.add(
            user_id=user_id,
            pii_types=pii_types,
            granted=granted,
            expires_at=datetime.utcnow() + timedelta(days=expiry_days),
        )

    def has_consent(self, user_id: str, pii_type: str) -> bool:
        """Vérifie si un utilisateur a un consentement valide pour un type de PII."""
        return self.consent_db.is_valid(user_id, pii_type)

    # ------------------------------------------------------------------
    # Piste d'audit
    # ------------------------------------------------------------------
    def log_access(self, user_id: str, pii_type: str, action: str):
        """Journalise un accès à une PII pour la piste d'audit RGPD."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "pii_type": pii_type,
            "action": action, # ex: 'view', 'export'
        }
        self._append_audit_log(log_entry)

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------
    def _mask(self, value: str, mask_char: str) -> str:
        """Masque une valeur en conservant les 2 premiers et 2 derniers caractères."""
        if len(value) <= 4:
            return mask_char * len(value)
        return value[:2] + mask_char * (len(value) - 4) + value[-2:]

    def _load_config(self, path: Optional[Path]) -> Dict:
        """Charge une configuration de rétention personnalisée si elle existe."""
        if path and path.exists():
            return json.loads(path.read_text())
        return RETENTION_RULES

    def _append_audit_log(self, entry: Dict):
        """Ajoute une entrée au fichier d'audit (format JSON Lines)."""
        try:
            audit_file = Path("logs/privacy_audit.jsonl")
            audit_file.parent.mkdir(exist_ok=True)
            with audit_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors de l'écriture dans le journal d'audit : {e}")


# ------------------------------------------------------------------
# Persistance du consentement (simple fichier JSONL)
# ------------------------------------------------------------------
class ConsentDB:
    """Une base de données simple, basée sur un fichier, pour stocker le consentement."""
    def __init__(self, config_path: Optional[Path]):
        self.file = Path(config_path or "data/consent.jsonl")

    def add(
        self, user_id: str, pii_types: List[str], granted: bool, expires_at: datetime
    ):
        """Ajoute un nouvel enregistrement de consentement."""
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
            logger.error(f"Erreur lors de l'écriture dans la base de données de consentement : {e}")

    def is_valid(self, user_id: str, pii_type: str) -> bool:
        """Vérifie si le consentement le plus récent pour un utilisateur et un type de PII est valide."""
        now = datetime.utcnow()
        try:
            with self.file.open("r", encoding="utf-8") as f:
                # Lit le fichier en sens inverse pour trouver le consentement le plus récent en premier.
                for line in reversed(list(f)):
                    record = json.loads(line)
                    if (
                        record["user_id"] == user_id
                        and pii_type in record["pii_types"]
                    ):
                        # Si le consentement est trouvé, vérifie s'il a expiré.
                        if datetime.fromisoformat(record["expires_at"]) < now:
                            return False
                        # Retourne l'état (accordé ou non).
                        return record["granted"]
        except FileNotFoundError:
            # Si le fichier n'existe pas, aucun consentement n'a été donné.
            pass
        return False


# ------------------------------------------------------------------
# Démonstration en ligne de commande
# ------------------------------------------------------------------
if __name__ == "__main__":
    policy = PrivacyPolicy()

    sample_text = (
        "Contactez-moi à jean.dupont@mail.fr ou au 06.12.34.56.78, "
        "ma carte est 4532-1234-5678-9012."
    )
    report = policy.scan_and_mask(sample_text)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
