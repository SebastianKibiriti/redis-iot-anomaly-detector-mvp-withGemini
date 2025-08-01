import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import redis
import time
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
              Input('interval-component', 'n_intervals'),
              State('live-update-graph', 'relayoutData'))
def update_graph_live(n, relayout_data):
    try:
        # Fetch the last 24 hours of data to keep the dashboard responsive.
        # Redis Time Series `range` uses millisecond timestamps.
        current_time_ms = int(time.time() * 1000)
        from_time_ms = current_time_ms - (24 * 60 * 60 * 1000) # 24 hours ago
        data = ts_client.range('device:01:temp', from_time_ms, '+')
    except Exception as e:
        print(f"Error querying Redis Time Series: {e}")
        return go.Figure()

    if not data:
        # If there's no data, show an empty graph with a message.
        fig = go.Figure()
        fig.update_layout(
            title='Live Temperature Readings',
            xaxis_title='Time',
            yaxis_title='Temperature (°C)',
            annotations=[
                dict(
                    text="No data available for the last 24 hours. Is the producer running?",
                    xref="paper", yref="paper", showarrow=False, font=dict(size=16)
                )
            ],
            yaxis=dict(range=[15, 30])
        )
        return fig

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
            yaxis=dict(
                range=[15, 30], # Keep a fixed range for better visual stability
                fixedrange=False # Allow the user to zoom on the y-axis
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
    )

    # Preserve the user's zoom/pan state across updates
    if relayout_data and 'xaxis.range[0]' in relayout_data:
        fig.update_layout(
            xaxis_range=[
                relayout_data['xaxis.range[0]'],
                relayout_data['xaxis.range[1]']
            ]
        )
    else:
        # Default to a 15-minute window with the latest data centered
        if not df.empty:
            last_timestamp = df['timestamp'].iloc[-1]
            # Center the view around the last data point with a 15-minute window
            start_time = last_timestamp - pd.Timedelta(minutes=7.5)
            end_time = last_timestamp + pd.Timedelta(minutes=7.5)
            fig.update_layout(xaxis_range=[start_time, end_time])

    return fig

if __name__ == '__main__':
    app.run(debug=True)
