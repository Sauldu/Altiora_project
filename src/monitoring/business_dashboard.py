# src/monitoring/business_dashboard.py
import dash_bootstrap_components as dbc
from dash import dash_table


class BusinessMetricsDashboard:
    """Dashboard orienté métriques métier QA"""

    def __init__(self):
        self.app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        self.setup_business_layout()

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
            ], className='mt-4')
        ])