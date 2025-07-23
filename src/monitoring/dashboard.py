# src/monitoring/dashboard.py
import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime, timedelta
import asyncio


class AltioraDashboard:
    def __init__(self, metrics_collector):
        self.app = dash.Dash(__name__)
        self.metrics = metrics_collector
        self.setup_layout()
        self.setup_callbacks()

    def setup_layout(self):
        """Configure le layout du dashboard"""
        self.app.layout = html.Div([
            html.H1('Altiora QA Assistant Monitoring'),

            # Auto-refresh toutes les 5 secondes
            dcc.Interval(id='interval-component', interval=5000),

            # Métriques en temps réel
            html.Div([
                html.Div([
                    html.H3('Model Response Time (P95)'),
                    dcc.Graph(id='response-time-graph')
                ], className='metric-card'),

                html.Div([
                    html.H3('Error Rate by Service'),
                    dcc.Graph(id='error-rate-graph')
                ], className='metric-card'),

                html.Div([
                    html.H3('Active Fine-tuning Jobs'),
                    html.Div(id='active-jobs-counter', className='big-number')
                ], className='metric-card'),
            ], className='metrics-row'),

            # Graphiques détaillés
            html.Div([
                dcc.Graph(id='token-usage-timeline'),
                dcc.Graph(id='model-performance-comparison')
            ], className='detailed-graphs')
        ])

    def setup_callbacks(self):
        """Configure les callbacks pour mise à jour temps réel"""

        @self.app.callback(
            Output('response-time-graph', 'figure'),
            Input('interval-component', 'n_intervals')
        )
        def update_response_time(n):
            # Récupération des métriques
            data = self.metrics.get_response_times(minutes=30)

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data['timestamp'],
                y=data['p95_response_time'],
                mode='lines+markers',
                name='P95 Response Time'
            ))

            fig.update_layout(
                yaxis_title="Response Time (ms)",
                xaxis_title="Time",
                showlegend=False
            )

            return fig

        @self.app.callback(
            Output('error-rate-graph', 'figure'),
            Input('interval-component', 'n_intervals')
        )
        def update_error_rate(n):
            data = self.metrics.get_error_rates()

            fig = go.Figure()
            for service in data['services']:
                fig.add_trace(go.Bar(
                    name=service['name'],
                    x=[service['name']],
                    y=[service['error_rate']]
                ))

            fig.update_layout(
                yaxis_title="Error Rate (%)",
                showlegend=False
            )

            return fig

        @self.app.callback(
            Output('active-jobs-counter', 'children'),
            Input('interval-component', 'n_intervals')
        )
        def update_active_jobs(n):
            count = self.metrics.get_active_training_jobs()
            return f"{count}"

    def run(self, debug=False, port=8050):
        """Lance le dashboard"""
        self.app.run_server(debug=debug, port=port, host='0.0.0.0')


# CSS personnalisé pour le dashboard
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


# src/monitoring/advanced_dashboard.py
class AdvancedDashboard(AltioraDashboard):
    """Dashboard avancé avec visualisations ML"""

    def __init__(self, metrics_collector, model_analyzer):
        super().__init__(metrics_collector)
        self.model_analyzer = model_analyzer
        self.add_ml_visualizations()

    def add_ml_visualizations(self):
        """Ajoute des visualisations spécifiques ML"""

        # Heatmap des performances par modèle
        @self.app.callback(
            Output('model-heatmap', 'figure'),
            Input('interval-component', 'n_intervals')
        )
        def update_model_heatmap(n):
            # Matrice de performance des modèles
            performance_matrix = self.model_analyzer.get_performance_matrix()

            fig = go.Figure(data=go.Heatmap(
                z=performance_matrix['values'],
                x=performance_matrix['metrics'],
                y=performance_matrix['models'],
                colorscale='RdYlGn'
            ))

            fig.update_layout(
                title='Model Performance Heatmap',
                xaxis_title='Metrics',
                yaxis_title='Models'
            )

            return fig

        # Graphique en temps réel de l'utilisation des tokens
        @self.app.callback(
            Output('token-usage-timeline', 'figure'),
            Input('interval-component', 'n_intervals')
        )
        def update_token_usage(n):
            # Données des 60 dernières minutes
            token_data = self.metrics.get_token_usage(minutes=60)

            fig = go.Figure()

            # Ligne pour chaque modèle
            for model in token_data['models']:
                fig.add_trace(go.Scatter(
                    x=token_data['timestamps'],
                    y=token_data[model],
                    mode='lines',
                    name=model,
                    stackgroup='one'  # Pour créer un graphique empilé
                ))

            fig.update_layout(
                title='Token Usage Over Time',
                xaxis_title='Time',
                yaxis_title='Tokens/min',
                hovermode='x unified'
            )

            return fig