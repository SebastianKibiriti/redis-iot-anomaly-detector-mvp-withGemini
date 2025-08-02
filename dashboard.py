import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import redis
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- Redis Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379

# A list of the available devices to display in the dropdown menu
DEVICE_IDS = ['01', '02', '03']

# --- Initialize Redis connection ---
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    ts_client = r.ts()
    print("Successfully connected to Redis for dashboard.")
except redis.exceptions.ConnectionError as e:
    print(f"Error connecting to Redis: {e}")
    exit(1)

# --- Dash App Setup ---
app = dash.Dash(__name__)

app.layout = html.Div(children=[
    html.H1(children='Real-time Temperature Monitoring Dashboard'),
    html.Div(children='Select a sensor to view its live temperature readings and anomalies.'),

    # --- New UI Element: Dropdown Menu for Sensor Selection ---
    html.Div([
        html.Label('Select a Sensor:'),
        dcc.Dropdown(
            id='sensor-selector',
            options=[{'label': f'Sensor {device_id}', 'value': device_id} for device_id in DEVICE_IDS],
            value=DEVICE_IDS[0],  # Set the default value to the first device
            clearable=False,
            style={'width': '200px', 'marginBottom': '20px'}
        ),
    ]),

    dcc.Graph(id='live-update-graph'),
    dcc.Interval(
        id='interval-component',
        interval=2*1000, # Update the graph every 2 seconds (in milliseconds)
        n_intervals=0
    )
])

# --- Callback to update the graph ---
@app.callback(
    Output('live-update-graph', 'figure'),
    Input('interval-component', 'n_intervals'),
    Input('sensor-selector', 'value')
)
def update_graph_live(n, selected_device_id):
    # Dynamically construct the Time Series key based on the selected device ID
    ts_key = f'device:{selected_device_id}:temp'
    
    # Query Redis Time Series for all data points
    try:
        data = ts_client.range(ts_key, '-', '+')
    except Exception as e:
        print(f"Error querying Redis Time Series for key '{ts_key}': {e}")
        return go.Figure()

    if not data:
        return go.Figure()

    # Convert the Redis data into a pandas DataFrame
    df = pd.DataFrame(data, columns=['timestamp', 'temperature'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Check for anomaly alerts
    anomaly_data = []
    try:
        # Use Redis SEARCH to find anomaly alerts for the selected device
        alerts = r.xrevrange('anomaly_alerts', max='+', min='-', count=100)
        for _, alert_bytes in alerts:
            alert = {k: v for k, v in alert_bytes.items()}
            if alert.get('device_id') == selected_device_id:
                anomaly_data.append({
                    'timestamp': pd.to_datetime(float(alert.get('timestamp')), unit='ms'),
                    'temperature': float(alert.get('temp_reading'))
                })
    except Exception as e:
        print(f"Error querying Redis for anomaly alerts: {e}")

    anomaly_df = pd.DataFrame(anomaly_data)

    # Create the Plotly figure with temperature and anomaly alerts
    fig = go.Figure()

    # Add the main temperature line
    fig.add_trace(go.Scatter(
        x=df['timestamp'], 
        y=df['temperature'], 
        mode='lines', 
        name='Temperature'
    ))

    # Add anomaly markers if any exist
    if not anomaly_df.empty:
        fig.add_trace(go.Scatter(
            x=anomaly_df['timestamp'],
            y=anomaly_df['temperature'],
            mode='markers',
            name='Anomaly Alert',
            marker=dict(color='red', size=10, symbol='circle')
        ))

    fig.update_layout(
        title=f'Live Temperature Readings for Sensor {selected_device_id}',
        xaxis_title='Time',
        yaxis_title='Temperature (°C)',
        yaxis=dict(
            range=[15, 30],
            fixedrange=False
        ),
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=15, label="15m", step="minute", stepmode="backward"),
                    dict(count=1, label="1h", step="hour", stepmode="backward"),
                    dict(count=6, label="6h", step="hour", stepmode="backward"),
                    dict(count=12, label="12h", step="hour", stepmode="backward"),
                    dict(step="all")
                ])
            ),
            rangeslider=dict(visible=True),
            type="date"
        )
    )

    return fig

if __name__ == '__main__':
    app.run_server(debug=True)
