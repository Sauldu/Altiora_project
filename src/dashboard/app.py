"""Tableau de bord de monitoring en temps réel pour Altiora.

Ce module implémente un tableau de bord interactif utilisant Dash (Plotly)
pour visualiser les métriques de performance de l'application Altiora.
Il se connecte à Prometheus pour récupérer les données et affiche des
indicateurs clés (nombre de requêtes, erreurs, temps de réponse) ainsi
que des graphiques d'évolution.
"""

import dash
from dash import dcc, html, callback, Output, Input
import plotly.graph_objs as go
import requests
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration Prometheus : URL de votre serveur Prometheus.
PROMETHEUS_URL = "http://localhost:9090"

# Initialisation de l'application Dash.
app = dash.Dash(__name__, title="Altiora Dashboard")

# Définition de la mise en page (layout) du tableau de bord.
app.layout = html.Div([
    html.H1("Altiora – Monitoring en temps réel", style={'textAlign': 'center'}),
    
    # Composant d'intervalle pour le rafraîchissement automatique des données.
    dcc.Interval(id='interval-component', interval=5_000, n_intervals=0), # Rafraîchit toutes les 5 secondes.

    # Cartes d'indicateurs clés (KPIs).
    html.Div([
        html.Div(id='card-requests', className='metric-card'),
        html.Div(id='card-errors', className='metric-card'),
        html.Div(id='card-avg-time', className='metric-card'),
    ], style={'display': 'flex', 'gap': '20px', 'padding': '20px'}),

    # Graphiques détaillés.
    dcc.Graph(id='graph-response-time'),
    dcc.Graph(id='graph-requests-rate'),
])

# ---------- Callbacks Dash ----------
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
    """Met à jour toutes les métriques et graphiques du tableau de bord."

    Cette fonction est appelée périodiquement par le composant `dcc.Interval`.
    Elle interroge Prometheus et met à jour les éléments de l'interface.

    Args:
        n_intervals: Le nombre d'intervalles écoulés (utilisé pour déclencher le callback).

    Returns:
        Un tuple de composants Dash mis à jour (cartes, figures de graphiques).
    """
    try:
        # 1. Récupération du nombre total de requêtes.
        total_requests_data = query_prometheus('altiora_requests_total')
        total_requests_val = float(total_requests_data[0]['value'][1]) if total_requests_data else 0

        # 2. Récupération du nombre d'erreurs (requêtes avec statut 4xx ou 5xx).
        errors_data = query_prometheus('altiora_requests_total{status=~"4..|5.."}')
        errors_val = float(errors_data[0]['value'][1]) if errors_data else 0

        # 3. Récupération du temps de réponse moyen sur la dernière minute.
        avg_time_data = query_prometheus('avg_over_time(altiora_response_time_seconds[1m])')
        avg_time_val = float(avg_time_data[0]['value'][1]) if avg_time_data else 0

        # Mise à jour des cartes d'indicateurs.
        card_requests_content = html.H3(f"{int(total_requests_val)} requêtes")
        card_errors_content = html.H3(f"{int(errors_val)} erreurs")
        card_avg_time_content = html.H3(f"{avg_time_val:.3f}s")

        # Graphique 1 : Temps de réponse (ligne).
        response_time_series = query_prometheus('altiora_response_time_seconds[5m]')
        times_rt, values_rt = parse_timeseries(response_time_series)

        fig_response_time = go.Figure(
            data=[go.Scatter(x=times_rt, y=values_rt, mode='lines', name='Temps de Réponse')],
            layout=go.Layout(title='Temps de réponse (5 dernières minutes)', yaxis_title='Secondes', xaxis_title='Temps')
        )

        # Graphique 2 : Taux de requêtes (barres).
        requests_rate_series = query_prometheus('rate(altiora_requests_total[1m])')
        times_rr, values_rr = parse_timeseries(requests_rate_series)

        fig_requests_rate = go.Figure(
            data=[go.Bar(x=times_rr, y=values_rr, name='Req/s')],
            layout=go.Layout(title='Taux de requêtes (1 dernière minute)', yaxis_title='Requêtes/seconde', xaxis_title='Temps')
        )

        return card_requests_content, card_errors_content, card_avg_time_content, fig_response_time, fig_requests_rate

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Erreur de connexion à Prometheus : {e}. Assurez-vous que Prometheus est en cours d'exécution sur {PROMETHEUS_URL}.")
        # Retourne des composants avec un message d'erreur en cas de problème de connexion.
        return [
            html.H3("N/A"),
            html.H3("N/A"),
            html.H3("N/A"),
        ], go.Figure(), go.Figure() # Retourne des figures vides.
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la mise à jour du tableau de bord : {e}", exc_info=True)
        return [
            html.H3("Erreur"),
            html.H3("Erreur"),
            html.H3("Erreur"),
        ], go.Figure(), go.Figure()

# ---------- Fonctions utilitaires ----------
def query_prometheus(query: str) -> list[dict]:
    """Interroge l'API Prometheus avec une requête PromQL."

    Args:
        query: La requête PromQL à exécuter.

    Returns:
        Une liste de dictionnaires contenant les résultats de la requête.

    Raises:
        requests.exceptions.RequestException: Si la requête HTTP échoue.
    """
    url = f"{PROMETHEUS_URL}/api/v1/query"
    resp = requests.get(url, params={'query': query}, timeout=5) # Timeout de 5 secondes.
    resp.raise_for_status() # Lève une exception pour les codes d'état HTTP 4xx/5xx.
    data = resp.json()
    return data['data']['result']


def parse_timeseries(series: list[dict]) -> tuple[list[datetime], list[float]]:
    """Parse une série temporelle Prometheus en listes de timestamps et de valeurs."

    Args:
        series: La liste des séries temporelles retournées par Prometheus.

    Returns:
        Un tuple de deux listes : la première contient les objets `datetime`,
        la seconde contient les valeurs flottantes.
    """
    if not series:
        return [], []

    times, values = [], []
    # Prometheus peut retourner plusieurs séries si la requête n'est pas agrégée.
    # Ici, on prend la première série trouvée.
    for point in series[0]['values']:
        timestamp, value = point
        times.append(datetime.fromtimestamp(timestamp)) # Convertit l'horodatage Unix en objet datetime.
        values.append(float(value))
    return times, values


# ---------- Lancement de l'application Dash ----------
if __name__ == '__main__':
    # Pour lancer ce tableau de bord, assurez-vous que Prometheus est en cours d'exécution
    # et collecte les métriques de votre application Altiora.
    logger.info(f"Lancement du tableau de bord Altiora sur http://0.0.0.0:8050")
    logger.info(f"Assurez-vous que Prometheus est accessible à : {PROMETHEUS_URL}")
    app.run_server(debug=True, host='0.0.0.0', port=8050)
