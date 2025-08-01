import redis
import time
import random
import json

# --- Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
STREAM_KEY = 'sensor:temperature:01'

# --- NEW: Anomaly Simulation Parameters ---
# The chance (as a percentage) to generate an anomaly on each cycle
ANOMALY_CHANCE = 5  # 5% chance of an anomaly per second

# The range for normal temperatures
NORMAL_TEMP_MIN = 20.0
NORMAL_TEMP_MAX = 25.0

# The range for anomalous temperatures
ANOMALY_TEMP_MIN = 30.0
ANOMALY_TEMP_MAX = 35.0

def generate_sensor_data():
    """
    Generates a dictionary of mock sensor data with a random chance of anomaly.
    """
    temperature = None
    humidity_percent = round(random.uniform(40.0, 60.0), 2)

    # Use random.randint to check if we should generate an anomaly
    if random.randint(1, 100) <= ANOMALY_CHANCE:
        # Generate an anomalous temperature
        temperature = round(random.uniform(ANOMALY_TEMP_MIN, ANOMALY_TEMP_MAX), 2)
    else:
        # Generate a normal temperature
        temperature = round(random.uniform(NORMAL_TEMP_MIN, NORMAL_TEMP_MAX), 2)

    return {
        "timestamp": time.time(),
        "temperature_c": temperature,
        "humidity_percent": humidity_percent
    }

def run_producer():
    """
    Connects to Redis and publishes mock sensor data to a stream.
    """
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        print("Successfully connected to Redis. Starting data production.")

        while True:
            data = generate_sensor_data()
            
            entry_id = r.xadd(STREAM_KEY, data)
            
            # Print a more informative message
            if data['temperature_c'] >= ANOMALY_TEMP_MIN or data['temperature_c'] <= NORMAL_TEMP_MIN:
                 print(f"**ANOMALY PRODUCED** Published entry {entry_id} with data: {data}")
            else:
                 print(f"Published entry {entry_id} to stream '{STREAM_KEY}' with data: {data}")
            
            time.sleep(1)

    except redis.exceptions.ConnectionError as e:
        print(f"Connection Error: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
        print("Please ensure your Docker container is running.")
    except KeyboardInterrupt:
        print("\nProducer stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    run_producer()
