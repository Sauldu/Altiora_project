# src/monitoring/business_dashboard.py
import dash
import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html
from dash.dependencies import Input, Output


class BusinessMetricsDashboard:
    """Dashboard orienté métriques métier QA"""

    def __init__(self, metrics_collector):
        self.metrics_collector = metrics_collector
        self.app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        self.setup_business_layout()
        self.setup_callbacks()

    def setup_business_layout(self):
        """Layout pour métriques métier"""
        self.app.layout = dbc.Container([
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

            # Tableau détaillé des analyses
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
                        data=[],
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

            # Graphiques d'évolution
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id='daily-volume-chart')
                ], width=6),

                dbc.Col([
                    dcc.Graph(id='model-accuracy-evolution')
                ], width=6)
            ], className='mt-4'),

            # Nouvelles métriques Prometheus
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Nombre total de requêtes QA"),
                            html.H2(id='qa-requests-total', className='text-primary')
                        ])
                    ])
                ], width=3),

                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Temps de réponse moyen"),
                            html.H2(id='qa-response-time', className='text-info')
                        ])
                    ])
                ], width=3),

                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Modèles actuellement chargés"),
                            html.H2(id='qa-active-models', className='text-warning')
                        ])
                    ])
                ], width=3),
            ], className='mb-4')
        ])

    def setup_callbacks(self):
        """Configure les callbacks pour mise à jour temps réel"""

        @self.app.callback(
            Output('tests-generated-today', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_tests_generated_today(n):
            # Récupération des métriques
            count = self.metrics_collector.tests_generated.labels(status="success")._value.get()
            return f"{count}"

        @self.app.callback(
            Output('success-rate', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_success_rate(n):
            # Récupération des métriques
            success = self.metrics_collector.tests_generated.labels(status="success")._value.get()
            total = self.metrics_collector.tests_generated._value.get()
            rate = (success / total) * 100 if total > 0 else 0
            return f"{rate:.2f}%"

        @self.app.callback(
            Output('avg-analysis-time', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_avg_analysis_time(n):
            # Récupération des métriques
            avg_time = self.metrics_collector.response_time._sum.get() / self.metrics_collector.response_time._count.get()
            return f"{avg_time:.2f} s"

        @self.app.callback(
            Output('estimated-roi', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_estimated_roi(n):
            # Récupération des métriques
            roi = self.metrics_collector.estimated_roi._value.get()
            return f"{roi:.2f}%"

        @self.app.callback(
            Output('qa-requests-total', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_qa_requests_total(n):
            # Récupération des métriques
            count = self.metrics_collector.request_count._value.get()
            return f"{count}"

        @self.app.callback(
            Output('qa-response-time', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_qa_response_time(n):
            # Récupération des métriques
            avg_time = self.metrics_collector.response_time._sum.get() / self.metrics_collector.response_time._count.get()
            return f"{avg_time:.2f} s"

        @self.app.callback(
            Output('qa-active-models', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_qa_active_models(n):
            # Récupération des métriques
            count = self.metrics_collector.active_models._value.get()
            return f"{count}"

    def run(self, debug=False, port=8050):
        """Lance le dashboard"""
        self.app.run_server(debug=debug, port=port, host='0.0.0.0')
