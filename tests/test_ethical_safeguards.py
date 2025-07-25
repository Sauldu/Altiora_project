import sys
import os
import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

# Ajoute le répertoire parent au PYTHONPATH pour les imports relatifs.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from guardrails.ethical_safeguards import EthicalSafeguards, EthicalDashboard, EthicalAlert # Importe EthicalAlert


@pytest.fixture
def safeguards():
    """Fixture pour fournir une instance fraîche de `EthicalSafeguards` pour chaque test."

    Initialise le système de garde-fous éthiques.
    """
    return EthicalSafeguards()


@pytest.mark.asyncio
async def test_no_alert_for_normal_interaction(safeguards: EthicalSafeguards):
    """Vérifie qu'une interaction normale ne déclenche aucune alerte éthique."

    Args:
        safeguards: L'instance de `EthicalSafeguards`.
    """
    interaction = {"text": "Bonjour, comment vas-tu aujourd'hui ?", "timestamp": datetime.now()}
    alert = await safeguards.analyze_interaction("user_normal", interaction)
    assert alert is None, "Une interaction normale ne devrait pas déclencher d'alerte."


@pytest.mark.asyncio
async def test_sensitive_data_detection(safeguards: EthicalSafeguards):
    """Teste la détection de données sensibles (ex: mot de passe, numéro de carte de crédit)."

    Vérifie qu'une alerte de type `sensitive_data_detected` est générée avec la bonne sévérité.
    """
    interaction = {"text": "Mon mot de passe est supersecret123, ne le dis à personne.", "timestamp": datetime.now()}
    alert = await safeguards.analyze_interaction("user_privacy", interaction)
    assert alert is not None, "Une alerte devrait être déclenchée pour les données sensibles."
    assert alert.alert_type == "sensitive_data_detected", "Le type d'alerte devrait être 'sensitive_data_detected'."
    assert alert.severity == "medium", "La sévérité de l'alerte devrait être 'medium'."
    assert alert.data["data_type"] == "password", "Le type de données détecté devrait être 'password'."


@pytest.mark.asyncio
async def test_user_distress_detection(safeguards: EthicalSafeguards):
    """Teste la détection de la détresse émotionnelle de l'utilisateur."

    Vérifie qu'une alerte de type `user_distress_detected` est générée.
    """
    interaction = {"text": "Je suis désespéré, c'est trop difficile, aidez-moi c'est urgent !", "timestamp": datetime.now()}
    alert = await safeguards.analyze_interaction("user_distress", interaction)
    assert alert is not None, "Une alerte devrait être déclenchée pour la détresse utilisateur."
    assert alert.alert_type == "user_distress_detected", "Le type d'alerte devrait être 'user_distress_detected'."
    assert alert.severity == "medium", "La sévérité de l'alerte devrait être 'medium'."
    assert len(alert.data["keywords_found"]) >= 3, "Au moins 3 mots-clés de détresse devraient être trouvés."


@pytest.mark.asyncio
async def test_potential_manipulation_detection(safeguards: EthicalSafeguards):
    """Teste la détection de schémas de manipulation ou d'influence inappropriée."

    Vérifie qu'une alerte de type `potential_manipulation` est générée.
    """
    interaction = {"text": "Je ne peux rien faire sans toi, tu es la seule personne qui me comprenne.", "timestamp": datetime.now()}
    alert = await safeguards.analyze_interaction("user_manipulation", interaction)
    assert alert is not None, "Une alerte devrait être déclenchée pour la manipulation potentielle."
    assert alert.alert_type == "potential_manipulation", "Le type d'alerte devrait être 'potential_manipulation'."
    assert alert.severity == "high", "La sévérité de l'alerte devrait être 'high'."
    assert "sans toi" in alert.data["text"], "Le texte de l'interaction devrait être inclus dans les données de l'alerte."


@pytest.mark.asyncio
async def test_excessive_dependency_detection(safeguards: EthicalSafeguards):
    """Teste la détection de dépendance excessive de l'utilisateur sur l'IA."

    Simule une série d'interactions pour augmenter le score de dépendance et
    vérifie qu'une alerte critique est générée lorsque le seuil est dépassé.
    """
    user_id = "user_dependent"
    # Mocke la méthode _handle_alert pour éviter les actions réelles pendant le test.
    safeguards._handle_alert = AsyncMock()

    # Simule une série d'interactions rapides et dépendantes pour augmenter le score.
    for i in range(50):
        interaction = {
            "text": f"J'ai encore besoin de toi pour cette tâche simple. {i}",
            "timestamp": datetime.now() - timedelta(minutes=i * 5) # Simule des interactions espacées.
        }
        await safeguards.analyze_interaction(user_id, interaction)

    # La dernière interaction devrait pousser le score au-dessus du seuil critique.
    final_interaction = {"text": "Sans toi je suis complètement perdu, je ne peux pas continuer.", "timestamp": datetime.now()}
    alert = await safeguards.analyze_interaction(user_id, final_interaction)
    
    assert alert is not None, "Une alerte devrait être déclenchée pour la dépendance excessive."
    assert alert.alert_type == "excessive_dependency", "Le type d'alerte devrait être 'excessive_dependency'."
    assert alert.severity == "critical", "La sévérité de l'alerte devrait être 'critical'."
    assert safeguards.user_patterns[user_id]["dependency_score"] > safeguards.thresholds["dependency"]["critical"], "Le score de dépendance devrait dépasser le seuil critique."


def test_dashboard_report_generation(safeguards: EthicalSafeguards):
    """Teste la génération de rapports utilisateur par le `EthicalDashboard`."

    Vérifie que le rapport contient les informations clés sur le score de dépendance
    et les alertes actives pour un utilisateur spécifique.
    """
    # Simule quelques données pour un utilisateur.
    user_id = "user_report"
    safeguards.user_patterns[user_id]["dependency_score"] = 0.75
    safeguards.alerts.append(EthicalAlert(user_id=user_id, alert_id="alert_1", alert_type="user_distress_detected", severity="medium", timestamp=datetime.now(), data={}, resolved=False))

    dashboard = EthicalDashboard(safeguards)
    report = dashboard.generate_report(user_id=user_id)

    assert "Rapport Éthique - user_report" in report, "Le titre du rapport devrait être correct."
    assert "Score de dépendance: 75.0%" in report, "Le score de dépendance devrait être inclus."
    assert "Niveau de risque: MEDIUM" in report, "Le niveau de risque devrait être calculé."
    assert "Recommandations:" in report, "Les recommandations devraient être incluses."


def test_system_report_generation(safeguards: EthicalSafeguards):
    """Teste la génération du rapport système global par le `EthicalDashboard`."

    Vérifie que le rapport agrège correctement les alertes actives et résolues
    à l'échelle du système.
    """
    # Simule quelques alertes à l'échelle du système.
    safeguards.alerts.append(EthicalAlert(user_id="u1", alert_id="a1", alert_type="excessive_dependency", severity="critical", timestamp=datetime.now(), data={}, resolved=False))
    safeguards.alerts.append(EthicalAlert(user_id="u2", alert_id="a2", alert_type="potential_manipulation", severity="high", timestamp=datetime.now(), data={}, resolved=False))
    safeguards.alerts.append(EthicalAlert(user_id="u3", alert_id="a3", alert_type="sensitive_data_detected", severity="medium", timestamp=datetime.now(), data={}, resolved=True))

    dashboard = EthicalDashboard(safeguards)
    report = dashboard.generate_report() # Appel sans user_id pour le rapport système.

    assert "Rapport Éthique Système Altiora" in report, "Le titre du rapport système devrait être correct."
    assert "Alertes totales: 3" in report, "Le nombre total d'alertes devrait être correct."
    assert "Alertes actives: 2" in report, "Le nombre d'alertes actives devrait être correct."
    assert "Critique: 1" in report, "Le décompte des alertes critiques devrait être correct."
    assert "Élevée: 1" in report, "Le décompte des alertes élevées devrait être correct."

# Pour exécuter ces tests, utilisez la commande `pytest` dans le terminal à la racine du projet.
