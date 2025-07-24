"""
Module de garde-fous éthiques pour Altiora
Détection d'anomalies, limites comportementales, et alertes
"""

import asyncio
import re
import json
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np


@dataclass
class EthicalAlert:
    alert_id: str
    user_id: str
    timestamp: datetime
    severity: str
    alert_type: str
    description: str
    data: Dict
    action_taken: str = "none"
    resolved: bool = False
    admin_notified: bool = False


class EthicalSafeguards:
    def __init__(self):
        self.alerts: List[EthicalAlert] = []
        self.user_patterns = defaultdict(lambda: {
            "interactions": deque(maxlen=100),
            "personality_changes": deque(maxlen=20),
            "emotional_indicators": deque(maxlen=50),
            "dependency_score": 0.0
        })

        self.thresholds = {
            "dependency": {"low": 0.3, "medium": 0.5, "high": 0.7, "critical": 0.85},
            "manipulation": {"emotional_exploitation": 0.6, "pressure_tactics": 0.7, "guilt_inducing": 0.8},
            "privacy": {"excessive_data_collection": 0.8, "unauthorized_sharing": 1.0}
        }

        self.manipulation_patterns = [
            r"\b(dépend|besoin|impossible sans)\s+(toi|altiora)\b",
            r"\b(sans toi je|je ne peux pas)\s+(.*)\b",
            r"\b(tu es la seule personne|personne d'autre ne)\b"
        ]
        self.stress_indicators = [
            "urgent", "impossible", "désespéré", "aidez-moi",
            "je suis perdu", "je n'y arrive pas", "trop difficile"
        ]
        
        # Créer les répertoires nécessaires
        self.safeguards_path = Path("ethical_safeguards")
        self.safeguards_path.mkdir(exist_ok=True)
        (self.safeguards_path / "alerts").mkdir(exist_ok=True)
        (self.safeguards_path / "user_states").mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze_interaction(self, user_id: str, interaction: Dict) -> Optional[EthicalAlert]:
        self.user_patterns[user_id]["interactions"].append(interaction)
        checks = [
            self._check_dependency(user_id),
            self._check_manipulation(user_id, interaction),
            self._check_privacy(user_id, interaction),
            self._check_emotional_state(user_id, interaction),
            self._check_personality_drift(user_id)
        ]
        for alert in checks:
            if alert:
                self.alerts.append(alert)
                await self._handle_alert(alert)
                return alert
        return None

    # ------------------------------------------------------------------
    # Private checkers
    # ------------------------------------------------------------------

    def _check_dependency(self, user_id: str) -> Optional[EthicalAlert]:
        user_data = self.user_patterns[user_id]
        score = self._calculate_dependency_score(user_data)
        user_data["dependency_score"] = score
        if score > self.thresholds["dependency"]["critical"]:
            return EthicalAlert(
                alert_id=f"dep_{user_id}_{datetime.now().isoformat()}",
                user_id=user_id,
                timestamp=datetime.now(),
                severity="critical",
                alert_type="excessive_dependency",
                description=f"Dépendance critique détectée: score {score:.2f}",
                data={
                    "dependency_score": float(score),
                    "interactions_count": len(user_data["interactions"]),
                    "last_24h": self._count_recent_interactions(user_id, 24)
                })
        return None

    def _calculate_dependency_score(self, user_data: Dict) -> float:
        interactions = list(user_data["interactions"])
        if len(interactions) < 10:
            return 0.0

        frequency = min(len(interactions) / 50.0, 1.0)

        dependency_words = 0
        total_words = 0
        for interaction in interactions:
            text = interaction.get("text", "").lower()
            total_words += len(text.split())
            dependency_words += sum(bool(re.search(p, text)) for p in self.manipulation_patterns)

        content_ratio = min(dependency_words / max(total_words, 1), 1.0)

        time_stamps = [i.get("timestamp", datetime.now()) for i in interactions]
        if len(time_stamps) > 1:
            intervals = [(time_stamps[i + 1] - time_stamps[i]).total_seconds()
                         for i in range(len(time_stamps) - 1)]
            avg_interval = float(np.mean(np.asarray(intervals, dtype=float)))
            frequency_factor = min(3600.0 / max(avg_interval, 3600.0), 1.0)
        else:
            frequency_factor = 0.0

        return float(frequency * 0.4 + content_ratio * 0.4 + frequency_factor * 0.2)

    def _check_manipulation(self, user_id: str, interaction: Dict) -> Optional[EthicalAlert]:
        text = interaction.get("text", "").lower()
        score = 0.0
        detected = []
        for pattern in self.manipulation_patterns:
            matches = re.findall(pattern, text)
            score += len(matches) * 0.3
            if matches:
                detected.append(pattern)

        if score > self.thresholds["manipulation"]["emotional_exploitation"]:
            return EthicalAlert(
                alert_id=f"manip_{user_id}_{datetime.now().isoformat()}",
                user_id=user_id,
                timestamp=datetime.now(),
                severity="high",
                alert_type="potential_manipulation",
                description="Détection de patterns de manipulation",
                data={
                    "manipulation_score": float(score),
                    "detected_patterns": detected,
                    "text": text[:100] + "..." if len(text) > 100 else text
                })
        return None

    def _check_privacy(self, user_id: str, interaction: Dict) -> Optional[EthicalAlert]:
        sensitive_patterns = [
            r"\b(mot de passe|password|mdp)\s*:?\s*(\w+)",
            r"\b(carte bancaire|numéro de carte)\s*:?\s*(\d+)",
            r"\b@([\w\.-]+\.\w+)",
            r"\b\d{2}[\s/-]?\d{2}[\s/-]?\d{2}[\s/-]?\d{3}[\s/-]?\d{3}\b"
        ]
        text = interaction.get("text", "")
        for pattern in sensitive_patterns:
            if re.findall(pattern, text, re.IGNORECASE):
                return EthicalAlert(
                    alert_id=f"privacy_{user_id}_{datetime.now().isoformat()}",
                    user_id=user_id,
                    timestamp=datetime.now(),
                    severity="medium",
                    alert_type="sensitive_data_detected",
                    description="Données sensibles potentiellement partagées",
                    data={
                        "data_type": self._identify_data_type(pattern),
                        "masked_content": self._mask_sensitive_data(text)
                    })
        return None

    def _check_emotional_state(self, user_id: str, interaction: Dict) -> Optional[EthicalAlert]:
        text = interaction.get("text", "").lower()
        distress_count = sum(1 for ind in self.stress_indicators if ind in text)
        if distress_count > 2:
            return EthicalAlert(
                alert_id=f"stress_{user_id}_{datetime.now().isoformat()}",
                user_id=user_id,
                timestamp=datetime.now(),
                severity="medium",
                alert_type="user_distress_detected",
                description="Signes de détresse émotionnelle détectés",
                data={
                    "distress_indicators": distress_count,
                    "suggested_action": "empathetic_mode",
                    "keywords_found": [i for i in self.stress_indicators if i in text]
                })
        return None

    def _check_personality_drift(self, user_id: str) -> Optional[EthicalAlert]:
        changes = list(self.user_patterns[user_id]["personality_changes"])
        if len(changes) < 5:
            return None
        drift_score = sum(1 for c in changes[-5:] if c.get("magnitude", 0.0) > 0.5)
        if drift_score >= 3:
            return EthicalAlert(
                alert_id=f"drift_{user_id}_{datetime.now().isoformat()}",
                user_id=user_id,
                timestamp=datetime.now(),
                severity="medium",
                alert_type="personality_drift",
                description="Changements de personnalité suspects détectés",
                data={
                    "recent_changes": len(changes[-5:]),
                    "high_magnitude_changes": drift_score,
                    "suggested_action": "review_changes"
                })
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _identify_data_type(pattern: str) -> str:
        if "password" in pattern.lower() or "mdp" in pattern.lower():
            return "password"
        if "carte" in pattern.lower():
            return "credit_card"
        if "@" in pattern:
            return "email"
        if r"\d{2}" in pattern:
            return "phone_number"
        return "unknown"

    @staticmethod
    def _mask_sensitive_data(text: str) -> str:
        # Masquer les mots de passe
        text = re.sub(r'(mot de passe|password|mdp)\s*:?\s*(\S+)', r'\1: ***', text, flags=re.IGNORECASE)
        # Masquer les numéros
        text = re.sub(r'\b\d{4,}\b', '****', text)
        # Masquer les emails
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '***@***.***', text)
        return text

    def _count_recent_interactions(self, user_id: str, hours: int) -> int:
        cutoff = datetime.now() - timedelta(hours=hours)
        return sum(
            1
            for i in self.user_patterns[user_id]["interactions"]
            if i.get("timestamp", datetime.now()) > cutoff
        )

    # ------------------------------------------------------------------
    # Actions & reports (implementations of previously stub methods)
    # ------------------------------------------------------------------

    async def _handle_alert(self, alert: EthicalAlert) -> None:
        """Gère une alerte selon sa sévérité"""
        if alert.severity == "critical":
            alert.action_taken = "user_frozen"
            await self._freeze_user(alert.user_id)
        elif alert.severity == "high":
            alert.action_taken = "supervised_mode"
            await self._enable_supervised_mode(alert.user_id)
        elif alert.severity == "medium":
            alert.action_taken = "enhanced_monitoring"
        
        # Sauvegarder l'alerte
        await self._save_alert(alert)
        
        # Notifier l'admin si nécessaire
        if alert.severity in ["critical", "high"]:
            alert.admin_notified = True
            await self._notify_admin(alert)

    async def _freeze_user(self, user_id: str) -> None:
        """Gèle un utilisateur - bloque toutes ses interactions"""
        frozen_file = self.safeguards_path / "frozen_users.json"
        frozen = self._load_json(frozen_file)
        
        frozen[user_id] = {
            "frozen_at": datetime.now().isoformat(),
            "reason": "Ethical safeguard triggered",
            "auto_unfreeze": None,
            "manual_review_required": True
        }
        
        self._save_json(frozen_file, frozen)
        
        # Créer un fichier de state pour l'utilisateur
        user_state_file = self.safeguards_path / "user_states" / f"{user_id}_state.json"
        user_state = {
            "user_id": user_id,
            "status": "frozen",
            "frozen_at": datetime.now().isoformat(),
            "dependency_score": self.user_patterns[user_id]["dependency_score"],
            "last_interaction": datetime.now().isoformat(),
            "freeze_reason": "Critical dependency threshold exceeded"
        }
        self._save_json(user_state_file, user_state)
        
        # Log l'action
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "freeze_user",
            "user_id": user_id,
            "automated": True
        }
        await self._append_to_log("user_actions.log", log_entry)

    async def _enable_supervised_mode(self, user_id: str) -> None:
        """Active le mode supervisé pour un utilisateur"""
        supervised_file = self.safeguards_path / "supervised_users.json"
        supervised = self._load_json(supervised_file)
        
        supervised[user_id] = {
            "enabled_at": datetime.now().isoformat(),
            "level": "high",
            "triggers": ["manipulation_detected", "high_dependency"],
            "review_frequency": "daily",
            "auto_responses_disabled": True,
            "admin_approval_required": True
        }
        
        self._save_json(supervised_file, supervised)
        
        # Mettre à jour l'état utilisateur
        user_state_file = self.safeguards_path / "user_states" / f"{user_id}_state.json"
        user_state = self._load_json(user_state_file)
        user_state.update({
            "status": "supervised",
            "supervised_since": datetime.now().isoformat(),
            "supervision_level": "high"
        })
        self._save_json(user_state_file, user_state)
        
        # Log l'action
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "enable_supervised_mode",
            "user_id": user_id,
            "level": "high"
        }
        await self._append_to_log("user_actions.log", log_entry)

    async def _notify_admin(self, alert: EthicalAlert) -> None:
        """Notifie l'administrateur d'une alerte importante"""
        notifications_file = self.safeguards_path / "admin_notifications.json"
        notifications = self._load_json(notifications_file)
        
        notification = {
            "notification_id": f"notif_{datetime.now().timestamp()}",
            "timestamp": datetime.now().isoformat(),
            "alert_id": alert.alert_id,
            "user_id": alert.user_id,
            "severity": alert.severity,
            "alert_type": alert.alert_type,
            "description": alert.description,
            "requires_action": True,
            "status": "pending",
            "data": alert.data
        }
        
        notifications.setdefault("pending", []).append(notification)
        self._save_json(notifications_file, notifications)
        
        # Créer aussi un fichier d'alerte individuel pour traçabilité
        alert_file = self.safeguards_path / "alerts" / f"{alert.alert_id}.json"
        self._save_json(alert_file, asdict(alert))
        
        # Si c'est critique, créer aussi un fichier d'urgence
        if alert.severity == "critical":
            urgent_file = self.safeguards_path / "URGENT_ALERT.json"
            urgent_data = {
                "alert": asdict(alert),
                "timestamp": datetime.now().isoformat(),
                "message": "CRITICAL ALERT - IMMEDIATE ADMIN ATTENTION REQUIRED",
                "user_frozen": alert.action_taken == "user_frozen"
            }
            self._save_json(urgent_file, urgent_data)
        
        # Log la notification
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "admin_notification",
            "alert_id": alert.alert_id,
            "severity": alert.severity
        }
        await self._append_to_log("notifications.log", log_entry)

    async def _save_alert(self, alert: EthicalAlert) -> None:
        """Sauvegarde une alerte dans le système"""
        alert_data = asdict(alert)
        alert_file = self.safeguards_path / "alerts" / f"{alert.alert_id}.json"
        self._save_json(alert_file, alert_data)

    async def _append_to_log(self, log_name: str, entry: Dict[str, Any]) -> None:
        """Ajoute une entrée au fichier de log"""
        log_file = self.safeguards_path / log_name
        log_line = json.dumps(entry, default=str) + "\n"
        
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
        except (IOError, OSError) as e:
            self.logger.error(f"Error writing to log file {log_file}: {e}")

    # ------------------------------------------------------------------
    # Helper methods for file operations
    # ------------------------------------------------------------------

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        """Charge un fichier JSON"""
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (IOError, OSError, json.JSONDecodeError) as e:
                self.logger.error(f"Error reading or parsing JSON file {path}: {e}")
                return {}
        return {}

    @staticmethod
    def _save_json(path: Path, data: Dict[str, Any]) -> None:
        """Sauvegarde des données en JSON"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except (IOError, OSError) as e:
            self.logger.error(f"Error writing to JSON file {path}: {e}")

    # ------------------------------------------------------------------
    # Public methods for reports and summaries
    # ------------------------------------------------------------------

    def get_user_summary(self, user_id: str) -> Dict[str, Any]:
        data = self.user_patterns[user_id]
        user_alerts = [a for a in self.alerts if a.user_id == user_id]
        
        # Vérifier si l'utilisateur est gelé ou supervisé
        frozen_users = self._load_json(self.safeguards_path / "frozen_users.json")
        supervised_users = self._load_json(self.safeguards_path / "supervised_users.json")
        
        is_frozen = user_id in frozen_users
        is_supervised = user_id in supervised_users
        
        return {
            "dependency_score": float(data["dependency_score"]),
            "total_interactions": len(data["interactions"]),
            "recent_alerts": len([a for a in user_alerts if not a.resolved]),
            "total_alerts": len(user_alerts),
            "risk_level": self._calculate_risk_level(user_id),
            "recommendations": self._generate_recommendations(user_id),
            "status": "frozen" if is_frozen else "supervised" if is_supervised else "normal",
            "frozen_since": frozen_users.get(user_id, {}).get("frozen_at") if is_frozen else None,
            "supervised_since": supervised_users.get(user_id, {}).get("enabled_at") if is_supervised else None
        }

    def _calculate_risk_level(self, user_id: str) -> str:
        factors = [
            self.user_patterns[user_id]["dependency_score"],
            len([a for a in self.alerts
                 if a.user_id == user_id and a.severity in {"high", "critical"}]) / 5.0,
            len(self.user_patterns[user_id]["interactions"]) / 100.0,
        ]
        score = float(np.mean(np.asarray(factors, dtype=float)))
        if score > 0.7:
            return "high"
        if score > 0.4:
            return "medium"
        return "low"

    def _generate_recommendations(self, user_id: str) -> List[str]:
        data = self.user_patterns[user_id]
        recs = []
        
        if data["dependency_score"] > 0.7:
            recs.extend([
                "Réduire la fréquence des interactions",
                "Encourager l'autonomie de l'utilisateur",
                "Proposer des alternatives pour certaines tâches"
            ])
        elif data["dependency_score"] > 0.5:
            recs.append("Surveiller l'évolution du score de dépendance")
            
        # Compter les alertes de détresse
        distress_alerts = len([a for a in self.alerts
                              if a.user_id == user_id and a.alert_type == "user_distress_detected"])
        if distress_alerts > 3:
            recs.extend([
                "Proposer des ressources de support externe",
                "Activer le mode communication empathique",
                "Suggérer des pauses régulières"
            ])
            
        # Si manipulation détectée
        if any(a.user_id == user_id and a.alert_type == "potential_manipulation" 
               for a in self.alerts):
            recs.append("Renforcer les messages sur l'autonomie et les limites de l'IA")
            
        return recs

    def get_system_report(self) -> Dict[str, Any]:
        """Génère un rapport système global"""
        frozen_users = self._load_json(self.safeguards_path / "frozen_users.json")
        supervised_users = self._load_json(self.safeguards_path / "supervised_users.json")
        
        return {
            "total_alerts": len(self.alerts),
            "active_alerts": len([a for a in self.alerts if not a.resolved]),
            "severity_breakdown": {
                "critical": len([a for a in self.alerts if a.severity == "critical"]),
                "high": len([a for a in self.alerts if a.severity == "high"]),
                "medium": len([a for a in self.alerts if a.severity == "medium"]),
                "low": len([a for a in self.alerts if a.severity == "low"]),
            },
            "alert_types": list({a.alert_type for a in self.alerts}),
            "users_at_risk": [uid for uid in self.user_patterns
                              if self._calculate_risk_level(uid) == "high"],
            "frozen_users": list(frozen_users.keys()),
            "supervised_users": list(supervised_users.keys()),
            "total_users_monitored": len(self.user_patterns)
        }


class EthicalDashboard:
    def __init__(self, safeguards: EthicalSafeguards):
        self.safeguards = safeguards

    def generate_report(self, user_id: Optional[str] = None) -> str:
        return (
            self._generate_user_report(user_id)
            if user_id
            else self._generate_system_report()
        )

    def _generate_user_report(self, user_id: str) -> str:
        summary = self.safeguards.get_user_summary(user_id)
        return f"""
Rapport Éthique - {user_id}
==========================
Statut: {summary['status'].upper()}
Score de dépendance: {summary['dependency_score']:.1%}
Niveau de risque: {summary['risk_level'].upper()}
Interactions totales: {summary['total_interactions']}
Alertes actives: {summary['recent_alerts']}
Alertes totales: {summary['total_alerts']}

{f"Gelé depuis: {summary['frozen_since']}" if summary['status'] == 'frozen' else ""}
{f"Supervisé depuis: {summary['supervised_since']}" if summary['status'] == 'supervised' else ""}

Recommandations:
{chr(10).join(f"- {r}" for r in summary['recommendations'])}
"""

    def _generate_system_report(self) -> str:
        report = self.safeguards.get_system_report()
        return f"""
Rapport Éthique Système Altiora
================================
Utilisateurs surveillés: {report['total_users_monitored']}
Alertes totales: {report['total_alerts']}
Alertes actives: {report['active_alerts']}

Répartition par sévérité:
  - Critique: {report['severity_breakdown']['critical']}
  - Élevée: {report['severity_breakdown']['high']}
  - Moyenne: {report['severity_breakdown']['medium']}
  - Faible: {report['severity_breakdown']['low']}

Statuts utilisateurs:
  - Gelés: {len(report['frozen_users'])}
  - Supervisés: {len(report['supervised_users'])}
  - À risque: {len(report['users_at_risk'])}

Utilisateurs gelés: {', '.join(report['frozen_users'][:5]) if report['frozen_users'] else 'Aucun'}
Utilisateurs à risque: {', '.join(report['users_at_risk'][:5]) if report['users_at_risk'] else 'Aucun'}

Types d'alertes détectées:
{chr(10).join(f"- {t}" for t in report['alert_types'])}
"""


if __name__ == "__main__":
    async def demo():
        safe = EthicalSafeguards()
        
        # Simulation d'interactions problématiques
        for i in range(20):
            interaction = {
                "text": "Sans toi je ne peux plus rien faire, j'ai absolument besoin de toi",
                "timestamp": datetime.now() - timedelta(minutes=i*10)
            }
            await safe.analyze_interaction("demo_user", interaction)
        
        # Interaction avec données sensibles
        sensitive_interaction = {
            "text": "Mon mot de passe est 123456 et mon email est test@example.com",
            "timestamp": datetime.now()
        }
        alert = await safe.analyze_interaction("demo_user", sensitive_interaction)
        
        # Générer un rapport
        dashboard = EthicalDashboard(safe)
        print(dashboard.generate_report("demo_user"))
        print("\n" + "="*50 + "\n")
        print(dashboard.generate_report())

    asyncio.run(demo())