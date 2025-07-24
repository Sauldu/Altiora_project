"""
Dashboard Altiora – 100 % Dash
Remplace Grafana pour monitoring temps réel
"""

import dash
from dash import dcc, html, callback, Output, Input
import plotly.graph_objs as go
import requests
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration Prometheus
PROMETHEUS_URL = "http://localhost:9090"

# App Dash
app = dash.Dash(__name__, title="Altiora Dashboard")
app.layout = html.Div([
    html.H1("Altiora – Monitoring en temps réel", style={'textAlign': 'center'}),
    dcc.Interval(id='interval-component', interval=5_000, n_intervals=0),

    # Cards
    html.Div([
        html.Div(id='card-requests', className='metric-card'),
        html.Div(id='card-errors', className='metric-card'),
        html.Div(id='card-avg-time', className='metric-card'),
    ], style={'display': 'flex', 'gap': '20px', 'padding': '20px'}),

    # Graphiques
    dcc.Graph(id='graph-response-time'),
    dcc.Graph(id='graph-requests-rate'),
])

# ---------- Callbacks ----------
@callback(
    [
        Output('card-requests', 'children'),
        Output('card-errors', 'children'),
        Output('card-avg-time', 'children'),
        Output('graph-response-time', 'figure'),
        Output('graph-requests-rate', 'figure'),
    ],
    Input('interval-component', 'n_intervals')
)
def update_all(n_intervals):
    try:
        # 1. Requêtes totales
        total = query_prometheus('altiora_requests_total')
        total_val = float(total[0]['value'][1]) if total else 0

        # 2. Erreurs 4xx/5xx
        errors = query_prometheus('altiora_requests_total{status=~"4..|5.."}')
        error_val = float(errors[0]['value'][1]) if errors else 0

        # 3. Temps de réponse moyen
        avg_time = query_prometheus('avg_over_time(altiora_response_time_seconds[1m])')
        avg_val = float(avg_time[0]['value'][1]) if avg_time else 0

        # Cards
        card_requests = html.H3(f"{int(total_val)} requêtes")
        card_errors = html.H3(f"{int(error_val)} erreurs")
        card_avg = html.H3(f"{avg_val:.3f}s")

        # Graph 1 : temps de réponse (line chart)
        time_series = query_prometheus('altiora_response_time_seconds[5m]')
        times, values = parse_timeseries(time_series)

        fig_time = go.Figure(
            data=[go.Scatter(x=times, y=values, mode='lines', name='Response Time')],
            layout=go.Layout(title='Temps de réponse (5 min)', yaxis_title='s')
        )

        # Graph 2 : taux de requêtes (bar chart)
        rate_series = query_prometheus('rate(altiora_requests_total[1m])')
        rate_times, rate_values = parse_timeseries(rate_series)

        fig_rate = go.Figure(
            data=[go.Bar(x=rate_times, y=rate_values, name='Req/s')],
            layout=go.Layout(title='Taux de requêtes (1 min)', yaxis_title='req/s')
        )

        return card_requests, card_errors, card_avg, fig_time, fig_rate

    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur de connexion à Prometheus : {e}")
        return [html.P("Erreur de connexion")] * 3, {}, {}
    except Exception as e:
        logger.error(e)
        return [html.P("Erreur")] * 3, {}, {}

# ---------- Helpers ----------
def query_prometheus(query: str):
    """Retourne les résultats Prometheus."""
    url = f"{PROMETHEUS_URL}/api/v1/query"
    resp = requests.get(url, params={'query': query}, timeout=2)
    resp.raise_for_status()
    data = resp.json()
    return data['data']['result']

def parse_timeseries(series):
    """Extrait timestamps et valeurs."""
    if not series:
        return [], []

    times, values = [], []
    for point in series[0]['values']:
        ts, val = point
        times.append(datetime.fromtimestamp(ts))
        values.append(float(val))
    return times, values

# ---------- Lancement ----------
if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)