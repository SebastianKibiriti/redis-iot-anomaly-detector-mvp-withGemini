import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import redis
import pandas as pd
import plotly.graph_objects as go

# --- Redis Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379

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
    html.Div(children='Visualizing data from Redis Time Series.'),

    dcc.Graph(id='live-update-graph'),
    dcc.Interval(
        id='interval-component',
        interval=2*1000, # Update the graph every 2 seconds (in milliseconds)
        n_intervals=0
    )
])

# --- Callback to update the graph ---
@app.callback(Output('live-update-graph', 'figure'),
              Input('interval-component', 'n_intervals'))
def update_graph_live(n):
    # Query Redis Time Series for the last 5 minutes of data
    # TS.RANGE key_name - 300000 +
    # The command returns a list of tuples: (timestamp_ms, value_str)
    try:
        data = ts_client.range('device:01:temp', '-', '+')
    except Exception as e:
        print(f"Error querying Redis Time Series: {e}")
        return go.Figure()

    if not data:
        return go.Figure()

    # Convert the Redis data into a pandas DataFrame
    df = pd.DataFrame(data, columns=['timestamp', 'temperature'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Create the Plotly figure
    fig = go.Figure(
        data=[
            go.Scatter(
                x=df['timestamp'], 
                y=df['temperature'], 
                mode='lines+markers', 
                name='Temperature'
            )
        ],
        layout=go.Layout(
            title='Live Temperature Readings',
            xaxis_title='Time',
            yaxis_title='Temperature (°C)',
            yaxis=dict(range=[15, 30]) # Set a fixed y-axis range for better visualization
        )
    )

    return fig

if __name__ == '__main__':
    app.run(debug=True)
