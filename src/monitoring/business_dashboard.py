# src/monitoring/business_dashboard.py
"""Module pour le tableau de bord des métriques métier de l'application Altiora.

Ce tableau de bord, construit avec Dash (Plotly), fournit une vue d'ensemble
des indicateurs clés de performance (KPI) métier, tels que le nombre de tests
générés, le taux de succès, le temps moyen d'analyse, et un ROI estimé.
Il est conçu pour être utilisé par les parties prenantes non techniques.
"""

import dash
import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html
from dash.dependencies import Input, Output


class BusinessMetricsDashboard:
    """Tableau de bord orienté métriques métier pour l'assurance qualité (QA)."""

    def __init__(self, metrics_collector):
        """Initialise le tableau de bord des métriques métier.

        Args:
            metrics_collector: Une instance d'un collecteur de métriques (ex: `MetricsCollector`)
                               fournissant les données nécessaires.
        """
        self.metrics_collector = metrics_collector
        # Initialise l'application Dash avec un thème Bootstrap pour un style moderne.
        self.app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        self.setup_business_layout()
        self.setup_callbacks()

    def setup_business_layout(self):
        """Configure la mise en page (layout) du tableau de bord avec les composants Dash."""
        self.app.layout = dbc.Container([
            # Composant d'intervalle pour le rafraîchissement automatique des données.
            dcc.Interval(id='interval-component', interval=5000, n_intervals=0), # Rafraîchit toutes les 5 secondes.

            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Tests générés aujourd'hui"),
                            html.H2(id='tests-generated-today', className='text-primary')
                        ])
                    ])
                ], width=3),

                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Taux de succès"),
                            html.H2(id='success-rate', className='text-success')
                        ])
                    ])
                ], width=3),

                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Temps moyen d'analyse"),
                            html.H2(id='avg-analysis-time', className='text-info')
                        ])
                    ])
                ], width=3),

                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("ROI estimé"),
                            html.H2(id='estimated-roi', className='text-warning')
                        ])
                    ])
                ], width=3),
            ], className='mb-4'),

            # Tableau détaillé des analyses récentes.
            dbc.Row([
                dbc.Col([
                    html.H3("Analyses récentes"),
                    dash_table.DataTable(
                        id='recent-analyses-table',
                        columns=[
                            {"name": "ID", "id": "id"},
                            {"name": "Type", "id": "type"},
                            {"name": "Statut", "id": "status"},
                            {"name": "Durée", "id": "duration"},
                            {"name": "Modèle", "id": "model"},
                            {"name": "Score", "id": "score"}
                        ],
                        data=[], # Les données seront mises à jour via un callback.
                        style_cell={'textAlign': 'center'},
                        style_data_conditional=[
                            {
                                'if': {'column_id': 'status', 'filter_query': '{status} = "Success"'},
                                'backgroundColor': '#d4edda',
                                'color': '#155724',
                            },
                            {
                                'if': {'column_id': 'status', 'filter_query': '{status} = "Failed"'},
                                'backgroundColor': '#f8d7da',
                                'color': '#721c24',
                            }
                        ]
                    )
                ], width=12)
            ]),

            # Graphiques d'évolution (ex: volume quotidien, précision du modèle).
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id='daily-volume-chart')
                ],
                 width=6),

                dbc.Col([
                    dcc.Graph(id='model-accuracy-evolution')
                ],
                 width=6)
            ], className='mt-4'),

            # Nouvelles métriques Prometheus (ex: requêtes totales, temps de réponse moyen, modèles actifs).
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Nombre total de requêtes QA"),
                            html.H2(id='qa-requests-total', className='text-primary')
                        ])
                    ])
                ],
                 width=3),

                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Temps de réponse moyen"),
                            html.H2(id='qa-response-time', className='text-info')
                        ])
                    ])
                ],
                 width=3),

                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Modèles actuellement chargés"),
                            html.H2(id='qa-active-models', className='text-warning')
                        ])
                    ])
                ],
                 width=3),
            ], className='mb-4')
        ])

    def setup_callbacks(self):
        """Configure les callbacks Dash pour la mise à jour en temps réel des métriques."""

        @self.app.callback(
            Output('tests-generated-today', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_tests_generated_today(n):
            """Met à jour le nombre de tests générés aujourd'hui."""
            # Récupération des métriques depuis le collecteur.
            count = self.metrics_collector.tests_generated.labels(status="success")._value.get()
            return f"{count}"

        @self.app.callback(
            Output('success-rate', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_success_rate(n):
            """Met à jour le taux de succès des tests."""
            success = self.metrics_collector.tests_generated.labels(status="success")._value.get()
            total = self.metrics_collector.tests_generated._value.get()
            rate = (success / total) * 100 if total > 0 else 0
            return f"{rate:.2f}%"

        @self.app.callback(
            Output('avg-analysis-time', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_avg_analysis_time(n):
            """Met à jour le temps moyen d'analyse."""
            # Assurez-vous que `response_time` est une métrique Prometheus de type Histogram.
            avg_time = self.metrics_collector.response_time._sum.get() / self.metrics_collector.response_time._count.get() if self.metrics_collector.response_time._count.get() > 0 else 0
            return f"{avg_time:.2f} s"

        @self.app.callback(
            Output('estimated-roi', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_estimated_roi(n):
            """Met à jour le ROI estimé."""
            # Cette métrique doit être fournie par le metrics_collector.
            roi = getattr(self.metrics_collector, 'estimated_roi', None)
            if roi:
                return f"{roi._value.get():.2f}%"
            return "N/A"

        @self.app.callback(
            Output('qa-requests-total', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_qa_requests_total(n):
            """Met à jour le nombre total de requêtes QA."""
            count = self.metrics_collector.request_count._value.get()
            return f"{count}"

        @self.app.callback(
            Output('qa-response-time', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_qa_response_time(n):
            """Met à jour le temps de réponse moyen des requêtes QA."""
            avg_time = self.metrics_collector.response_time._sum.get() / self.metrics_collector.response_time._count.get() if self.metrics_collector.response_time._count.get() > 0 else 0
            return f"{avg_time:.2f} s"

        @self.app.callback(
            Output('qa-active-models', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_qa_active_models(n):
            """Met à jour le nombre de modèles actuellement chargés."""
            # Cette métrique doit être fournie par le metrics_collector.
            active_models = getattr(self.metrics_collector, 'active_models', None)
            if active_models:
                return f"{active_models._value.get()}"
            return "N/A"

        # TODO: Implémenter les callbacks pour 'recent-analyses-table', 'daily-volume-chart', 'model-accuracy-evolution'

    def run(self, debug: bool = False, port: int = 8050):
        """Lance le tableau de bord Dash."

        Args:
            debug: Active le mode débogage de Dash.
            port: Le port sur lequel le tableau de bord écoutera.
        """
        self.app.run_server(debug=debug, port=port, host='0.0.0.0')


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    from prometheus_client import generate_latest, REGISTRY
    from src.monitoring.metrics_collector import MetricsCollector
    import time

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Crée un collecteur de métriques factice pour la démonstration.
    class MockMetricsCollector(MetricsCollector):
        def __init__(self):
            super().__init__()
            # Initialise des valeurs pour les métriques utilisées dans le dashboard.
            self.tests_generated.labels(status="success").inc(15)
            self.tests_generated.labels(status="failed").inc(2)
            self.request_count.inc(100)
            self.response_time.observe(0.5)
            self.response_time.observe(1.2)
            self.response_time.observe(0.8)
            self.active_models = Gauge('qa_active_models', 'Number of loaded models')
            self.active_models.set(3)
            self.estimated_roi = Gauge('estimated_roi', 'Estimated ROI')
            self.estimated_roi.set(12.5)

    metrics_collector = MockMetricsCollector()
    dashboard = BusinessMetricsDashboard(metrics_collector)

    print("\n--- Lancement du tableau de bord des métriques métier ---")
    print("Accédez au tableau de bord via votre navigateur à http://localhost:8050")
    print("Appuyez sur Ctrl+C pour arrêter le serveur.")

    # Lance le serveur Dash.
    dashboard.run(debug=True, port=8050)