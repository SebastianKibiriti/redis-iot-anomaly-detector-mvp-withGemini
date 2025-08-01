import redis
import time
import random
import json

# --- Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
STREAM_KEY = 'sensor:temperature:01' # The name of our Redis Stream

def generate_sensor_data():
    """
    Generates a dictionary of mock sensor data, occasionally including anomalies.
    """
    # There's a 1 in 10 chance of generating an anomalous temperature
    if random.randint(1, 10) == 1:
        # 50% chance for a high anomaly, 50% for a low one
        if random.random() < 0.5:
            temperature = 35.0  # High anomaly
        else:
            temperature = 15.0  # Low anomaly
    else:
        # 90% of the time, generate a normal temperature
        temperature = round(random.uniform(20.0, 26.0), 2)

    return {
        "timestamp": time.time(),
        "temperature_c": temperature,
        "humidity_percent": round(random.uniform(40.0, 60.0), 2)
    }

def run_producer():
    """
    Connects to Redis and publishes mock sensor data to a stream.
    """
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        print("Successfully connected to Redis. Starting data production.")

        # This loop will run indefinitely, publishing new data every second
        while True:
            # Generate a new data point
            data = generate_sensor_data()
            
            # The xadd command appends a new entry to the stream
            # The '*' tells Redis to automatically generate a unique ID for the entry
            # data is a dictionary of field/value pairs for the stream entry
            entry_id = r.xadd(STREAM_KEY, data)
            
            print(f"Published entry {entry_id} to stream '{STREAM_KEY}' with data: {data}")
            
            time.sleep(1) # Wait for 1 second before the next entry

    except redis.exceptions.ConnectionError as e:
        print(f"Connection Error: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
        print("Please ensure your Redis container is running.")
    except KeyboardInterrupt:
        print("\nProducer stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    run_producer()
