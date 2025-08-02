import redis
import json
import time
from flask import Flask, render_template
from datetime import datetime

# --- Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
TS_KEY = 'device:01:temp'

# --- Redis Connection ---
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    ts_client = r.ts()
    if not r.ping():
        raise redis.exceptions.ConnectionError("Could not ping Redis server.")
    print("Successfully connected to Redis for dashboard.")
except redis.exceptions.ConnectionError as e:
    print(f"ERROR: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Please ensure it's running.")
    print(f"Error details: {e}")
    exit(1)

# --- Flask App Setup ---
app = Flask(__name__)

# Cache for dashboard data
dashboard_data_cache = {
    'temperature': [],
    'moving_average': [],
    'std_dev_upper': [],
    'std_dev_lower': [],
    'timestamps': []
}

@app.route('/')
def index():
    """
    Renders the main dashboard page.
    """
    return render_template('dashboard.html')

@app.route('/data')
def get_data():
    """
    Returns the latest sensor data, moving average, and standard deviation bounds.
    """
    try:
        # Fetch the last 100 data points from the Time Series
        data_points = ts_client.range(TS_KEY, '-', '+', count=100)
        
        # We need at least a certain number of points to perform the statistical calculation
        if len(data_points) < 100:
            return json.dumps(dashboard_data_cache)

        values = [float(val) for ts, val in data_points]
        timestamps = [int(ts) for ts, val in data_points]

        # Calculate the moving average
        moving_average = sum(values) / len(values)

        # Calculate the standard deviation
        variance = sum([(v - moving_average) ** 2 for v in values]) / len(values)
        standard_deviation = variance ** 0.5
        
        # Calculate the anomaly bounds
        std_dev_upper = moving_average + (2 * standard_deviation)
        std_dev_lower = moving_average - (2 * standard_deviation)

        # Update the cache
        dashboard_data_cache['temperature'] = values
        dashboard_data_cache['moving_average'] = [moving_average] * len(values)
        dashboard_data_cache['std_dev_upper'] = [std_dev_upper] * len(values)
        dashboard_data_cache['std_dev_lower'] = [std_dev_lower] * len(values)
        dashboard_data_cache['timestamps'] = [datetime.fromtimestamp(ts / 1000).strftime('%H:%M:%S') for ts in timestamps]
        
    except Exception as e:
        print(f"Error fetching data from Redis: {e}")
        # In case of error, just return the last known data
        pass

    return json.dumps(dashboard_data_cache)

if __name__ == '__main__':
    app.run(debug=True)
