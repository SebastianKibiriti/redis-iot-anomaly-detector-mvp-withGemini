import redis
import json
import time
from flask import Flask, render_template, request, jsonify
from datetime import datetime

# --- Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
TS_KEY = 'device:01:temp'
PARAMS_KEY = 'dashboard_params'

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
    Renders the main dashboard page with the current parameters.
    """
    # Fetch current parameters from Redis to display on the form
    params = r.hgetall(PARAMS_KEY)
    if not params:
        # Set default parameters if they don't exist
        params = {'window_size': '100', 'std_dev_multiplier': '2'}
        r.hset(PARAMS_KEY, mapping=params)
    return render_template('dashboard.html', current_params=params)

@app.route('/set_params', methods=['POST'])
def set_params():
    """
    Sets the user-defined parameters in Redis.
    """
    try:
        window_size = int(request.form.get('window_size', 100))
        std_dev_multiplier = int(request.form.get('std_dev_multiplier', 2))
        
        # Store parameters in a Redis hash
        r.hset(PARAMS_KEY, mapping={'window_size': window_size, 'std_dev_multiplier': std_dev_multiplier})
        
        return jsonify({'status': 'success', 'message': 'Parameters updated successfully.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/data')
def get_data():
    """
    Returns the latest sensor data, moving average, and standard deviation bounds.
    """
    try:
        # Fetch parameters from Redis
        params = r.hgetall(PARAMS_KEY)
        window_size = int(params.get('window_size', 100))
        std_dev_multiplier = int(params.get('std_dev_multiplier', 2))

        # Fetch the last 'window_size' data points from the Time Series
        data_points = ts_client.range(TS_KEY, '-', '+', count=window_size)
        
        if len(data_points) < window_size:
            return json.dumps(dashboard_data_cache)

        values = [float(val) for ts, val in data_points]
        timestamps = [int(ts) for ts, val in data_points]

        # Calculate the moving average
        moving_average = sum(values) / len(values)

        # Calculate the standard deviation
        variance = sum([(v - moving_average) ** 2 for v in values]) / len(values)
        standard_deviation = variance ** 0.5
        
        # Calculate the anomaly bounds using the multiplier from Redis
        std_dev_upper = moving_average + (std_dev_multiplier * standard_deviation)
        std_dev_lower = moving_average - (std_dev_multiplier * standard_deviation)

        # Update the cache
        dashboard_data_cache['temperature'] = values
        dashboard_data_cache['moving_average'] = [moving_average] * len(values)
        dashboard_data_cache['std_dev_upper'] = [std_dev_upper] * len(values)
        dashboard_data_cache['std_dev_lower'] = [std_dev_lower] * len(values)
        dashboard_data_cache['timestamps'] = [datetime.fromtimestamp(ts / 1000).strftime('%H:%M:%S') for ts in timestamps]
        
    except Exception as e:
        print(f"Error fetching data from Redis: {e}")
        pass

    return json.dumps(dashboard_data_cache)

if __name__ == '__main__':
    app.run(debug=True)
