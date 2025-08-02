import redis
import json
import time
import os
from datetime import datetime

# --- Configuration ---
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
INPUT_STREAM_KEY = 'sensor:temperature:01' # The stream our producer sends to
CONSUMER_GROUP_NAME = 'anomaly_detector_group'
CONSUMER_NAME = 'processor-01' # Unique name for this consumer instance
ANOMALY_ALERTS_STREAM = 'anomaly_alerts'
PARAMS_KEY = 'dashboard_params' # The key where we store user-defined params

# --- Redis Connection ---
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    ts_client = r.ts()
    if not r.ping():
        raise redis.exceptions.ConnectionError("Could not ping Redis server.")
    print("Successfully connected to Redis for stream processing.")
except redis.exceptions.ConnectionError as e:
    print(f"ERROR: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Please ensure it's running.")
    print(f"Error details: {e}")
    exit(1)

def create_consumer_group():
    """
    Creates the consumer group if it doesn't already exist.
    """
    try:
        r.xgroup_create(INPUT_STREAM_KEY, CONSUMER_GROUP_NAME, id='0', mkstream=True)
        print(f"Consumer group '{CONSUMER_GROUP_NAME}' created for stream '{INPUT_STREAM_KEY}'.")
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"Consumer group '{CONSUMER_GROUP_NAME}' already exists.")
        else:
            print(f"Error creating consumer group: {e}")
            exit(1)

def check_for_anomaly(ts_client, device_id, temperature, window_size, std_dev_multiplier):
    """
    Performs statistical anomaly detection using moving average and standard deviation.
    """
    ts_key = f"device:{device_id}:temp"

    try:
        data_points = ts_client.range(ts_key, '-', '+', count=window_size)
        
        if len(data_points) < window_size:
            return False, None, None

        values = [float(val) for ts, val in data_points]

        moving_average = sum(values) / len(values)

        variance = sum([(v - moving_average) ** 2 for v in values]) / len(values)
        standard_deviation = variance ** 0.5
        
        upper_bound = moving_average + (std_dev_multiplier * standard_deviation)
        lower_bound = moving_average - (std_dev_multiplier * standard_deviation)
        
        is_anomaly = not (lower_bound <= temperature <= upper_bound)
        
        return is_anomaly, moving_average, standard_deviation

    except Exception as e:
        print(f"Error during statistical anomaly check for device {device_id}: {e}")
        return False, None, None

def _process_and_ack_message(message_id, message_data, params):
    """
    Helper function to process a single message, check for anomalies, and acknowledge.
    """
    try:
        window_size = int(params.get('window_size', 100))
        std_dev_multiplier = int(params.get('std_dev_multiplier', 2))

        decoded_data = {k: v for k, v in message_data.items()}
        timestamp_ms = int(float(decoded_data.get('timestamp')) * 1000)
        temperature = float(decoded_data.get('temperature_c'))
        device_id = INPUT_STREAM_KEY.split(':')[-1]
        ts_key = f"device:{device_id}:temp"

        # Anomaly Detection Logic with dynamic parameters
        is_anomaly, moving_average, standard_deviation = check_for_anomaly(ts_client, device_id, temperature, window_size, std_dev_multiplier)

        if is_anomaly:
            alert_data = {
                'device_id': device_id,
                'type': 'statistical_anomaly',
                'temp_reading': temperature,
                'moving_average': moving_average,
                'standard_deviation': standard_deviation,
                'timestamp': timestamp_ms
            }
            r.xadd(ANOMALY_ALERTS_STREAM, alert_data)
            print(f"*** ANOMALY DETECTED! *** Published alert to '{ANOMALY_ALERTS_STREAM}'.")

        ts_client.add(ts_key, timestamp_ms, temperature, retention_msecs=(30 * 24 * 60 * 60 * 1000), labels={'unit': 'celsius', 'device': device_id})
        r.xack(INPUT_STREAM_KEY, CONSUMER_GROUP_NAME, message_id)
    except Exception as ex:
        print(f"CRITICAL ERROR: Failed to process message {message_id}. Reason: {ex}")

def process_messages():
    """
    Reads messages from the stream, checks for anomalies, stores data in Time Series, and acknowledges.
    """
    print(f"Starting consumer '{CONSUMER_NAME}' in group '{CONSUMER_GROUP_NAME}' for stream '{INPUT_STREAM_KEY}'...")

    # --- RECOVERY LOGIC ---
    print("Checking for pending messages to recover...")
    while True:
        try:
            # Fetch parameters from Redis before processing starts
            messages = r.xreadgroup(
                groupname=CONSUMER_GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={INPUT_STREAM_KEY: '0'},
                count=1,
                block=1000
            )

            if not messages or not messages[0][1]:
                print("No pending messages found. Starting live stream processing.")
                break

            for stream_name, stream_messages in messages:
                params = r.hgetall(PARAMS_KEY) # Fetch params for this batch
                for message_id, message_data in stream_messages:
                    _process_and_ack_message(message_id, message_data, params)
                        
        except redis.exceptions.ConnectionError as e:
            print(f"Lost connection to Redis during recovery. Retrying in 5 seconds... Error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"An unhandled error occurred in the recovery loop: {e}")
            time.sleep(1)

    # --- NORMAL OPERATION LOOP ---
    while True:
        try:
            # Fetch parameters from Redis at the start of each loop iteration
            messages = r.xreadgroup(
                groupname=CONSUMER_GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={INPUT_STREAM_KEY: '>'},
                count=1,
                block=1000
            )

            if not messages:
                time.sleep(0.1)
                continue

            for stream_name, stream_messages in messages:
                params = r.hgetall(PARAMS_KEY) # Fetch params for this batch
                for message_id, message_data in stream_messages:
                    _process_and_ack_message(message_id, message_data, params)
                        
        except redis.exceptions.ConnectionError as e:
            print(f"Lost connection to Redis. Retrying in 5 seconds... Error: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nProcessor stopped by user.")
            break
        except Exception as e:
            print(f"An unhandled error occurred in the main loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    create_consumer_group()
    process_messages()