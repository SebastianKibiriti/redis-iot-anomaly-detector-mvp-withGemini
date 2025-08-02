import redis
import json
import time
from datetime import datetime

# --- Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
INPUT_STREAM_KEYS = ['sensor:temperature:01', 'sensor:temperature:02', 'sensor:temperature:03'] # The streams our producer sends to
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
    print("Successfully connected to Redis for multi-sensor stream processing.")
except redis.exceptions.ConnectionError as e:
    print(f"ERROR: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Please ensure it's running.")
    print(f"Error details: {e}")
    exit(1)

def create_consumer_group():
    """
    Creates the consumer group for each stream if it doesn't already exist.
    """
    for stream_key in INPUT_STREAM_KEYS:
        try:
            r.xgroup_create(stream_key, CONSUMER_GROUP_NAME, id='0', mkstream=True)
            print(f"Consumer group '{CONSUMER_GROUP_NAME}' created for stream '{stream_key}'.")
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                print(f"Consumer group '{CONSUMER_GROUP_NAME}' already exists for stream '{stream_key}'.")
            else:
                print(f"Error creating consumer group for stream '{stream_key}': {e}")
                exit(1)

def check_for_anomaly(r, ts_client, device_id, temperature, window_size, std_dev_multiplier):
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

def process_messages():
    """
    Reads messages from all streams, checks for anomalies, stores data in Time Series, and acknowledges.
    """
    print(f"Starting consumer '{CONSUMER_NAME}' in group '{CONSUMER_GROUP_NAME}' for all streams...")

    # Create a dictionary of streams to read from with '>' as the ID for new messages
    streams_to_read = {key: '>' for key in INPUT_STREAM_KEYS}
    
    while True:
        try:
            # This single xreadgroup command reads from all defined streams at once
            messages = r.xreadgroup(
                groupname=CONSUMER_GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams=streams_to_read,
                count=1,
                block=1000
            )

            if not messages:
                time.sleep(0.1)
                continue

            for stream_name, stream_messages in messages:
                for message_id, message_data_bytes in stream_messages:
                    try:
                        decoded_data = {k: v for k, v in message_data_bytes.items()}
                        timestamp_ms = int(float(decoded_data.get('timestamp')) * 1000)
                        temperature = float(decoded_data.get('temperature_c'))
                        
                        # Dynamically get the device_id from the stream name
                        device_id = stream_name.split(':')[-1]
                        ts_key = f"device:{device_id}:temp"

                        # Anomaly Detection Logic with dynamic parameters
                        params = r.hgetall(PARAMS_KEY)
                        window_size = int(params.get('window_size', 100))
                        std_dev_multiplier = int(params.get('std_dev_multiplier', 2))
                        is_anomaly, moving_average, standard_deviation = check_for_anomaly(r, ts_client, device_id, temperature, window_size, std_dev_multiplier)
                        
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
                            print(f"*** ANOMALY DETECTED for device {device_id}! *** Published alert to '{ANOMALY_ALERTS_STREAM}'.")

                        ts_client.add(ts_key, timestamp_ms, temperature,
                                      retention_msecs=2592000000,
                                      labels={'unit': 'celsius', 'device': device_id}
                                     )
                        
                        r.xack(stream_name, CONSUMER_GROUP_NAME, message_id)
                        
                    except Exception as ex:
                        print(f"An unexpected error occurred processing message {message_id}: {ex}")
                        
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
