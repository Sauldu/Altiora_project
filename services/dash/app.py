import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from prometheus_client import CollectorRegistry, Gauge, start_http_server
import redis
import os

# Initialisation Dash
app = dash.Dash(__name__, external_stylesheets=['https://stackpath.bootstrapcdn.com/bootswatch/4.5.2/flatly/bootstrap.min.css'])

# Connexion Redis
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))

# Métriques Prometheus
registry = CollectorRegistry()
gauge_tests = Gauge('altiora_tests_total', 'Total tests generated', registry=registry)

# Layout Dash
app.layout = html.Div([
    html.H1("Altiora Dashboard", className="text-center mb-4"),

    dcc.Interval(id='interval', interval=5000, n_intervals=0),

    html.Div([
        html.Div([
            html.H3("Tests Generated"),
            html.H2(id='tests-count', className="text-primary"),
        ], className="col-md-4"),

        html.Div([
            html.H3("Memory Usage"),
            dcc.Graph(id='memory-graph'),
        ], className="col-md-8"),
    ], className="row"),

    html.Div([
        html.H3("Recent Sessions"),
        html.Ul(id='sessions-list')
    ], className="mt-4")
])


# Callbacks
@app.callback(
    [Output('tests-count', 'children'),
     Output('memory-graph', 'figure'),
     Output('sessions-list', 'children')],
    [Input('interval', 'n_intervals')]
)
def update_dashboard(n):
    # Tests count
    tests = redis_client.get("altiora:tests:count") or 0

    # Memory usage (simulation)
    memory_usage = [50, 60, 55, 70, 65, 80]
    fig = go.Figure(go.Scatter(y=memory_usage, mode='lines+markers'))
    fig.update_layout(height=300, margin={'l': 20, 'r': 20, 't': 20, 'b': 20})

    # Sessions
    sessions = [f"Session {i}" for i in range(3)]

    return (
        str(tests),
        fig,
        [html.Li(session) for session in sessions]
    )


if __name__ == '__main__':
    start_http_server(8005, registry=registry)  # Métriques Prometheus
    app.run_server(host='0.0.0.0', port=8050, debug=False)