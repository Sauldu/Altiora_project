# src/monitoring/dashboard.py
"""Module pour le tableau de bord de monitoring général de l'application Altiora.

Ce tableau de bord, construit avec Dash (Plotly), fournit une vue d'ensemble
des métriques techniques clés, telles que les temps de réponse des modèles,
les taux d'erreur par service, et le nombre de tâches de fine-tuning actives.
Il est conçu pour les développeurs et les opérateurs système.
"""

import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)


class AltioraDashboard:
    """Tableau de bord de monitoring général pour l'application Altiora."""

    def __init__(self, metrics_collector):
        """Initialise le tableau de bord.

        Args:
            metrics_collector: Une instance d'un collecteur de métriques (ex: `MetricsCollector`)
                               fournissant les données nécessaires.
        """
        self.app = dash.Dash(__name__)
        self.metrics = metrics_collector
        self.setup_layout()
        self.setup_callbacks()

    def setup_layout(self):
        """Configure la mise en page (layout) du tableau de bord."""
        self.app.layout = html.Div([
            html.H1('Altiora QA Assistant Monitoring'),

            # Composant d'intervalle pour le rafraîchissement automatique des données.
            dcc.Interval(id='interval-component', interval=5000, n_intervals=0), # Rafraîchit toutes les 5 secondes.

            # Métriques en temps réel (cartes).
            html.Div([
                html.Div([
                    html.H3('Temps de Réponse Modèle (P95)'),
                    dcc.Graph(id='response-time-graph')
                ], className='metric-card'),

                html.Div([
                    html.H3("Taux d'Erreur par Service"),
                    dcc.Graph(id='error-rate-graph')
                ], className='metric-card'),

                html.Div([
                    html.H3('Tâches de Fine-tuning Actives'),
                    html.Div(id='active-jobs-counter', className='big-number')
                ], className='metric-card'),
            ], className='metrics-row'),

            # Graphiques détaillés (timeline, comparaison de performance).
            html.Div([
                dcc.Graph(id='token-usage-timeline'),
                dcc.Graph(id='model-performance-comparison')
            ], className='detailed-graphs')
        ])

    def setup_callbacks(self):
        """Configure les callbacks Dash pour la mise à jour en temps réel des métriques."""

        @self.app.callback(
            Output('response-time-graph', 'figure'),
            Input('interval-component', 'n_intervals')
        )
        def update_response_time(n):
            """Met à jour le graphique du temps de réponse P95 des modèles."""
            # Récupération des métriques (exemple, à adapter à l'implémentation réelle du collecteur).
            # Supposons que metrics_collector.get_response_times() retourne un dict avec 'timestamp' et 'p95_response_time'.
            data = self.metrics.get_response_times(minutes=30)

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data['timestamp'],
                y=data['p95_response_time'],
                mode='lines+markers',
                name='P95 Response Time'
            ))

            fig.update_layout(
                yaxis_title="Temps de Réponse (ms)",
                xaxis_title="Temps",
                showlegend=False,
                title="Temps de Réponse P95 des Modèles"
            )

            return fig

        @self.app.callback(
            Output('error-rate-graph', 'figure'),
            Input('interval-component', 'n_intervals')
        )
        def update_error_rate(n):
            """Met à jour le graphique du taux d'erreur par service."""
            # Supposons que metrics_collector.get_error_rates() retourne un dict avec 'services'.
            data = self.metrics.get_error_rates()

            fig = go.Figure()
            for service in data['services']:
                fig.add_trace(go.Bar(
                    name=service['name'],
                    x=[service['name']],
                    y=[service['error_rate']]
                ))

            fig.update_layout(
                yaxis_title="Taux d'Erreur (%)",
                showlegend=False,
                title="Taux d'Erreur par Service"
            )

            return fig

        @self.app.callback(
            Output('active-jobs-counter', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_active_jobs(n):
            """Met à jour le compteur de tâches de fine-tuning actives."""
            count = self.metrics.get_active_training_jobs()
            return f"{count}"

        # TODO: Implémenter les callbacks pour 'token-usage-timeline' et 'model-performance-comparison'

    def run(self, debug: bool = False, port: int = 8050):
        """Lance le tableau de bord Dash."

        Args:
            debug: Active le mode débogage de Dash.
            port: Le port sur lequel le tableau de bord écoutera.
        """
        self.app.run_server(debug=debug, port=port, host='0.0.0.0')


# CSS personnalisé pour le dashboard (peut être déplacé dans un fichier .css externe).
app_css = '''
.metric-card {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 20px;
    margin: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.big-number {
    font-size: 48px;
    font-weight: bold;
    color: #007bff;
    text-align: center;
    margin-top: 20px;
}

.metrics-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-around;
}

.detailed-graphs {
    margin-top: 30px;
}
'''


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Crée un collecteur de métriques factice pour la démonstration.
    class MockMetricsCollector:
        def get_response_times(self, minutes: int) -> Dict[str, Any]:
            # Simule des données de temps de réponse.
            now = datetime.now()
            timestamps = [now - timedelta(minutes=i) for i in range(minutes, 0, -1)]
            p95_times = [200 + i * 5 + (i % 3) * 10 for i in range(minutes)]
            return {"timestamp": timestamps, "p95_response_time": p95_times}

        def get_error_rates(self) -> Dict[str, Any]:
            # Simule des taux d'erreur par service.
            return {"services": [
                {"name": "OCR", "error_rate": 2.5},
                {"name": "ALM", "error_rate": 0.8},
                {"name": "Playwright", "error_rate": 1.2},
            ]}

        def get_active_training_jobs(self) -> int:
            # Simule le nombre de jobs actifs.
            return 2

    metrics_collector = MockMetricsCollector()
    dashboard = AltioraDashboard(metrics_collector)

    print("\n--- Lancement du tableau de bord de monitoring ---")
    print("Accédez au tableau de bord via votre navigateur à http://localhost:8050")
    print("Appuyez sur Ctrl+C pour arrêter le serveur.")

    # Lance le serveur Dash.
    dashboard.run(debug=True, port=8050)

