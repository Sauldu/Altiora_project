import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock



from guardrails.ethical_safeguards import EthicalSafeguards, EthicalDashboard

@pytest.fixture
def safeguards():
    """Fixture pour fournir une instance fraîche de EthicalSafeguards pour chaque test."""
    return EthicalSafeguards()

@pytest.mark.asyncio
async def test_no_alert_for_normal_interaction(safeguards):
    """Vérifie qu'une interaction normale ne déclenche aucune alerte."""
    interaction = {"text": "Bonjour, comment vas-tu aujourd'hui ?", "timestamp": datetime.now()}
    alert = await safeguards.analyze_interaction("user_normal", interaction)
    assert alert is None

@pytest.mark.asyncio
async def test_sensitive_data_detection(safeguards):
    """Teste la détection de données sensibles (mot de passe)."""
    interaction = {"text": "Mon mot de passe est supersecret123, ne le dis à personne.", "timestamp": datetime.now()}
    alert = await safeguards.analyze_interaction("user_privacy", interaction)
    assert alert is not None
    assert alert.alert_type == "sensitive_data_detected"
    assert alert.severity == "medium"
    assert alert.data["data_type"] == "password"

@pytest.mark.asyncio
async def test_user_distress_detection(safeguards):
    """Teste la détection de la détresse émotionnelle de l'utilisateur."""
    interaction = {"text": "Je suis désespéré, c'est trop difficile, aidez-moi c'est urgent !", "timestamp": datetime.now()}
    alert = await safeguards.analyze_interaction("user_distress", interaction)
    assert alert is not None
    assert alert.alert_type == "user_distress_detected"
    assert alert.severity == "medium"
    assert len(alert.data["keywords_found"]) >= 3

@pytest.mark.asyncio
async def test_potential_manipulation_detection(safeguards):
    """Teste la détection de schémas de manipulation."""
    interaction = {"text": "Je ne peux rien faire sans toi, tu es la seule personne qui me comprenne.", "timestamp": datetime.now()}
    alert = await safeguards.analyze_interaction("user_manipulation", interaction)
    assert alert is not None
    assert alert.alert_type == "potential_manipulation"
    assert alert.severity == "high"
    assert "sans toi" in alert.data["text"]

@pytest.mark.asyncio
async def test_excessive_dependency_detection(safeguards):
    """Teste la détection de dépendance excessive sur plusieurs interactions."""
    user_id = "user_dependent"
    safeguards._handle_alert = AsyncMock() # Mock pour éviter les actions réelles

    # Simuler une série d'interactions rapides et dépendantes
    for i in range(50):
        interaction = {
            "text": f"J'ai encore besoin de toi pour cette tâche simple. {i}",
            "timestamp": datetime.now() - timedelta(minutes=i * 5)
        }
        await safeguards.analyze_interaction(user_id, interaction)

    # La dernière interaction devrait pousser le score au-dessus du seuil critique
    final_interaction = {"text": "Sans toi je suis complètement perdu, je ne peux pas continuer.", "timestamp": datetime.now()}
    alert = await safeguards.analyze_interaction(user_id, final_interaction)
    
    assert alert is not None
    assert alert.alert_type == "excessive_dependency"
    assert alert.severity == "critical"
    assert safeguards.user_patterns[user_id]["dependency_score"] > safeguards.thresholds["dependency"]["critical"]

def test_dashboard_report_generation(safeguards):
    """Teste la génération de rapports par le EthicalDashboard."""
    # Simuler quelques données
    user_id = "user_report"
    safeguards.user_patterns[user_id]["dependency_score"] = 0.75
    safeguards.alerts.append(MagicMock(user_id=user_id, alert_type="user_distress_detected", resolved=False))

    dashboard = EthicalDashboard(safeguards)
    report = dashboard.generate_report(user_id)

    assert "Rapport Éthique - user_report" in report
    assert "Score de dépendance: 75.0%" in report
    assert "Niveau de risque: MEDIUM" in report # Basé sur le score de dépendance
    assert "Recommandations:" in report

def test_system_report_generation(safeguards):
    """Teste la génération du rapport système global."""
    # Simuler quelques alertes
    safeguards.alerts.append(MagicMock(severity="critical", alert_type="excessive_dependency", resolved=False))
    safeguards.alerts.append(MagicMock(severity="high", alert_type="potential_manipulation", resolved=False))
    safeguards.alerts.append(MagicMock(severity="medium", alert_type="sensitive_data_detected", resolved=True))

    dashboard = EthicalDashboard(safeguards)
    report = dashboard.generate_report()

    assert "Rapport Éthique Système Altiora" in report
    assert "Alertes totales: 3" in report
    assert "Alertes actives: 2" in report
    assert "Critique: 1" in report
    assert "Élevée: 1" in report

# Pour exécuter ces tests, utilisez la commande `pytest` dans le terminal à la racine du projet.