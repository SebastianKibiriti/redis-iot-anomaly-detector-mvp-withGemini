# --- dashboard.py ---

import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import redis
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

# --- (Redis configuration and app setup remains the same) ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
PARAMS_KEY = 'dashboard_params'
DEVICE_IDS = ['01', '02', '03']
ALERT_STREAM_KEY = 'anomaly_alerts'

try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    ts_client = r.ts()
    if not r.ping():
        raise redis.exceptions.ConnectionError("Could not ping Redis server.")
    print("Successfully connected to Redis for dashboard.")
except redis.exceptions.ConnectionError as e:
    print(f"Error connecting to Redis: {e}")
    exit(1)

app = dash.Dash(__name__)

app.layout = html.Div(children=[
    html.H1(children='Real-time Temperature Monitoring Dashboard'),
    html.Div(children='Select a sensor to view its live temperature readings and anomalies.'),
    html.Div([
        html.Label('Select a Sensor:'),
        dcc.Dropdown(
            id='sensor-selector',
            options=[{'label': f'Sensor {device_id}', 'value': device_id} for device_id in DEVICE_IDS],
            value=DEVICE_IDS[0],
            clearable=False,
            style={'width': '200px', 'marginBottom': '20px'}
        ),
        dcc.Checklist(
            id='live-view-toggle',
            options=[{'label': 'Live View', 'value': 'live'}],
            value=['live'],
            style={'marginBottom': '20px'}
        ),
    ]),
    # --- UI Elements for Parameter Control ---
    html.Div([
        html.Label('Std Dev Multiplier:', style={'marginRight': '10px'}),
        dcc.Input(
            id='std-dev-input',
            type='number',
            value=2,
            min=0,
            step=0.1,
            style={'marginRight': '10px'}
        ),
        html.Button('Update Parameters', id='update-button', n_clicks=0),
        html.Div(id='update-output', style={'marginTop': '10px'})
    ], style={'marginBottom': '20px'}),

    dcc.Graph(id='live-update-graph'),
    dcc.Interval(
        id='interval-component',
        interval=2*1000,
        n_intervals=0
    )
])


# --- Callback to update the graph ---
@app.callback(
    Output('live-update-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('sensor-selector', 'value'),
     Input('live-view-toggle', 'value')]
)
def update_graph_live(n, selected_device_id, live_view_status):
    ts_key = f'device:{selected_device_id}:temp'
    
    params = r.hgetall(PARAMS_KEY)
    window_size = int(params.get('window_size', 100))
    std_dev_multiplier = float(params.get('std_dev_multiplier', 2.0))

    # --- FIX: Fetch data by count to match the processor's logic ---
    try:
        # Use revrange to get the latest N points, which is what the processor's logic implies.
        # Fetch a larger number (1000) to ensure the rolling window is accurate for the visible data.
        data = ts_client.revrange(ts_key, '-', '+', count=1000)
        data.reverse() # revrange returns newest first, so reverse to get chronological order.
    except Exception as e:
        print(f"Error querying Redis Time Series for key '{ts_key}': {e}")
        return go.Figure()

    if not data:
        return go.Figure()

    df = pd.DataFrame(data, columns=['timestamp', 'temperature'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df['timestamp'] = df['timestamp'].dt.tz_convert('Africa/Johannesburg')
    df['temperature'] = pd.to_numeric(df['temperature'])
    
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['temperature'], mode='lines', name='Temperature'
    ))
    
    if len(df) > 1:
        # --- FIX: Shift the data to calculate bounds based on *past* data, matching the processor ---
        window_size = int(params.get('window_size', 100))
        # The processor checks a new point against the stats of the *previous* `window_size` points.
        # Shifting the series makes the rolling calculation use the window of data *before* each point.
        shifted_temp = df['temperature'].shift(1)
        rolling_stats = shifted_temp.rolling(window=window_size, min_periods=1)
        moving_average = rolling_stats.mean()
        standard_deviation = rolling_stats.std()

        # Replace NaN from initial periods with the first valid value
        moving_average = moving_average.bfill()
        standard_deviation = standard_deviation.bfill()

        std_dev_multiplier = float(params.get('std_dev_multiplier', 2.0))
        std_dev_upper = moving_average + (std_dev_multiplier * standard_deviation)
        std_dev_lower = moving_average - (std_dev_multiplier * standard_deviation)

        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=moving_average, mode='lines', 
            name='Moving Average', line=dict(color='orange', dash='dot')
        ))
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=std_dev_upper, mode='lines', 
            name='Upper Bound', line=dict(color='red', dash='dash')
        ))
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=std_dev_lower, mode='lines', 
            name='Lower Bound', line=dict(color='red', dash='dash')
        ))

    anomaly_data = []
    try:
        alerts = r.xrevrange(ALERT_STREAM_KEY, max='+', min='-', count=100)
        for _, alert_bytes in alerts:
            alert = {k: v for k, v in alert_bytes.items()}
            if alert.get('device_id') == selected_device_id:
                # Ensure all expected keys are present before appending
                if all(k in alert for k in ['timestamp', 'temp_reading', 'moving_average', 'standard_deviation']):
                    anomaly_data.append({
                        'timestamp': float(alert.get('timestamp')),
                        'temperature': float(alert.get('temp_reading')),
                        'moving_average': float(alert.get('moving_average')),
                        'standard_deviation': float(alert.get('standard_deviation'))
                    })
    except Exception as e:
        print(f"Error querying Redis for anomaly alerts: {e}")

    anomaly_df = pd.DataFrame(anomaly_data)

    if not anomaly_df.empty:
        anomaly_df['timestamp'] = pd.to_datetime(anomaly_df['timestamp'], unit='ms', utc=True)
        anomaly_df['timestamp'] = anomaly_df['timestamp'].dt.tz_convert('Africa/Johannesburg')
        
        std_dev_multiplier = float(params.get('std_dev_multiplier', 2.0))
        anomaly_df['upper_bound'] = anomaly_df['moving_average'] + (std_dev_multiplier * anomaly_df['standard_deviation'])
        anomaly_df['lower_bound'] = anomaly_df['moving_average'] - (std_dev_multiplier * anomaly_df['standard_deviation'])

        fig.add_trace(go.Scatter(
            x=anomaly_df['timestamp'], y=anomaly_df['temperature'], mode='markers',
            name='Anomaly Alert', marker=dict(color='red', size=10, symbol='circle')
        ))
        
        # --- FIX: Add markers for the specific bounds at the time of each anomaly ---
        fig.add_trace(go.Scatter(
            x=anomaly_df['timestamp'], y=anomaly_df['upper_bound'], mode='markers',
            name='Anomaly Upper Bound', marker=dict(color='purple', size=11, symbol='cross-thin'),
            hoverinfo='skip'
        ))
        fig.add_trace(go.Scatter(
            x=anomaly_df['timestamp'], y=anomaly_df['lower_bound'], mode='markers',
            name='Anomaly Lower Bound', marker=dict(color='purple', size=11, symbol='cross-thin'),
            hoverinfo='skip'
        ))

    # --- START OF THE FIX ---
    fig.update_layout(
        title=f'Live Temperature Readings for Sensor {selected_device_id}',
        xaxis_title='Time',
        yaxis_title='Temperature (°C)',
        yaxis=dict(fixedrange=False),
        xaxis=dict(
            rangeslider=dict(visible=True),
            type="date"
        )
    )

    # The `live_view_status` will be a list, e.g., ['live'] if checked, or [] if unchecked.
    if live_view_status:
        # LIVE MODE: Calculate the last 60 seconds and force the view to update.
        latest_time = df['timestamp'].iloc[-1]
        start_time = latest_time - timedelta(seconds=60)
        fig.update_layout(
            xaxis_range=[start_time, latest_time],
            uirevision=time.time() # Use a dynamic uirevision to force the redraw
        )
    else:
        # MANUAL MODE: Use a static uirevision to preserve user's zoom.
        fig.update_layout(uirevision=selected_device_id)
    
    return fig

# --- Callback: Handles the button click to update parameters in Redis ---
@app.callback(
    Output('update-output', 'children'),
    Input('update-button', 'n_clicks'),
    State('std-dev-input', 'value')
)
def update_parameters_to_redis(n_clicks, std_dev_value):
    if n_clicks > 0:
        try:
            r.hset(PARAMS_KEY, 'std_dev_multiplier', std_dev_value)
            return f"Parameters updated successfully at {datetime.now().strftime('%H:%M:%S')}!"
        except Exception as e:
            return f"Error updating parameters: {e}"
    return ""

if __name__ == '__main__':
    app.run(debug=True)