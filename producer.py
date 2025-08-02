import redis
import time
import random
import json

# --- Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379

# The names of our Redis Streams, one for each sensor
STREAM_KEYS = ['sensor:temperature:01', 'sensor:temperature:02', 'sensor:temperature:03']

def generate_sensor_data():
    """
    Generates a dictionary of mock sensor data with a slightly different temperature
    range for each device to make it more realistic.
    """
    device_id = random.choice(['01', '02', '03'])
    
    if device_id == '01':
        temp = round(random.uniform(18.0, 22.0), 2)
    elif device_id == '02':
        temp = round(random.uniform(20.0, 25.0), 2)
    else: # device_id == '03'
        temp = round(random.uniform(23.0, 27.0), 2)

    return {
        "device_id": device_id,
        "timestamp": time.time(),
        "temperature_c": temp,
        "humidity_percent": round(random.uniform(40.0, 60.0), 2)
    }

def run_producer():
    """
    Connects to Redis and publishes mock sensor data to one of the multiple streams.
    """
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        print("Successfully connected to Redis. Starting multi-sensor data production.")

        while True:
            # Generate a new data point
            data = generate_sensor_data()
            
            # Select the stream key based on the generated device_id
            stream_key = f"sensor:temperature:{data['device_id']}"
            
            # The xadd command appends a new entry to the stream
            entry_id = r.xadd(stream_key, data)
            
            print(f"Published entry {entry_id} to stream '{stream_key}' with data: {data}")
            
            time.sleep(0.5) # Publish a new entry every half a second

    except redis.exceptions.ConnectionError as e:
        print(f"Connection Error: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
        print("Please ensure your Redis container is running.")
    except KeyboardInterrupt:
        print("\nProducer stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    run_producer()
