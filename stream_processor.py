import redis
import json
import time

# --- Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
INPUT_STREAM_KEY = 'sensor:temperature:01'
CONSUMER_GROUP_NAME = 'anomaly_detector_group'
CONSUMER_NAME = 'processor-01'

# --- Anomaly Detection Thresholds and Stream ---
MIN_TEMP = 18.0
MAX_TEMP = 28.0
ANOMALY_ALERTS_STREAM = 'anomaly_alerts'

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

def check_for_anomaly(r, ts_client, device_id, temperature, window_size=100, std_dev_multiplier=2):
    """
    Performs statistical anomaly detection using moving average and standard deviation.
    """
    ts_key = f"device:{device_id}:temp"

    try:
        # Fetch the last 'window_size' data points
        # The timestamp '-' and '+' represent the oldest and newest data points in the Time Series
        # The last parameter is the count
        data_points = ts_client.range(ts_key, '-', '+', count=window_size)
        
        # We need at least 'window_size' points to perform a good calculation
        if len(data_points) < window_size:
            return False, None, None

        # Extract just the temperature values from the list of [timestamp, value] pairs
        values = [float(val) for ts, val in data_points]

        # Calculate the moving average
        moving_average = sum(values) / len(values)

        # Calculate the standard deviation
        variance = sum([(v - moving_average) ** 2 for v in values]) / len(values)
        standard_deviation = variance ** 0.5
        
        # Define the threshold for an anomaly
        upper_bound = moving_average + (std_dev_multiplier * standard_deviation)
        lower_bound = moving_average - (std_dev_multiplier * standard_deviation)
        
        # Check if the current temperature is an anomaly
        is_anomaly = not (lower_bound <= temperature <= upper_bound)
        
        return is_anomaly, moving_average, standard_deviation

    except Exception as e:
        print(f"Error during statistical anomaly check for device {device_id}: {e}")
        return False, None, None

def process_messages():
    """
    Reads messages from the stream, checks for anomalies, stores data in Time Series, and acknowledges.
    """
    print(f"Starting consumer '{CONSUMER_NAME}' in group '{CONSUMER_GROUP_NAME}' for stream '{INPUT_STREAM_KEY}'...")

    # --- RECOVERY LOGIC ---
    print("Checking for pending messages to recover...")
    while True:
        try:
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
                for message_id, message_data_bytes in stream_messages:
                    try:
                        decoded_data = {k: v for k, v in message_data_bytes.items()}
                        timestamp_ms = int(float(decoded_data.get('timestamp')) * 1000)
                        temperature = float(decoded_data.get('temperature_c'))
                        device_id = INPUT_STREAM_KEY.split(':')[-1]
                        ts_key = f"device:{device_id}:temp"

                        # Anomaly Detection Logic
                        is_anomaly, moving_average, standard_deviation = check_for_anomaly(r, ts_client, device_id, temperature)
                        
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

                        ts_client.add(ts_key, timestamp_ms, temperature,
                                      retention_msecs=2592000000,
                                      labels={'unit': 'celsius', 'device': device_id}
                                     )
                        
                        r.xack(INPUT_STREAM_KEY, CONSUMER_GROUP_NAME, message_id)
                    except Exception as ex:
                        print(f"CRITICAL ERROR (RECOVERY): Failed to process message {message_id}. Reason: {ex}")
                        
        except redis.exceptions.ConnectionError as e:
            print(f"Lost connection to Redis during recovery. Retrying in 5 seconds... Error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"An unhandled error occurred in the recovery loop: {e}")
            time.sleep(1)

    # --- NORMAL OPERATION LOOP ---
    while True:
        try:
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
                for message_id, message_data_bytes in stream_messages:
                    try:
                        decoded_data = {k: v for k, v in message_data_bytes.items()}
                        timestamp_ms = int(float(decoded_data.get('timestamp')) * 1000)
                        temperature = float(decoded_data.get('temperature_c'))
                        device_id = INPUT_STREAM_KEY.split(':')[-1]
                        ts_key = f"device:{device_id}:temp"

                        # Anomaly Detection Logic
                        is_anomaly, moving_average, standard_deviation = check_for_anomaly(r, ts_client, device_id, temperature)
                        
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

                        ts_client.add(ts_key, timestamp_ms, temperature,
                                      retention_msecs=2592000000,
                                      labels={'unit': 'celsius', 'device': device_id}
                                     )
                        
                        r.xack(INPUT_STREAM_KEY, CONSUMER_GROUP_NAME, message_id)
                        
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
