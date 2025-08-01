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

def process_messages():
    """
    Reads messages from the stream, checks for anomalies, stores data in Time Series, and acknowledges.
    """
    print(f"Starting consumer '{CONSUMER_NAME}' in group '{CONSUMER_GROUP_NAME}' for stream '{INPUT_STREAM_KEY}'...")

    # --- RECOVERY LOGIC ---
    print("Checking for pending messages to recover...")
    while True:
        try:
            # The special stream ID '0' tells xreadgroup to read from the PEL
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
                    print(f"RECOVERY: Processing pending message ID: {message_id}")
                    try:
                        decoded_data = {k: v for k, v in message_data_bytes.items()}
                        timestamp_ms = int(float(decoded_data.get('timestamp')) * 1000)
                        temperature = float(decoded_data.get('temperature_c'))
                        device_id = INPUT_STREAM_KEY.split(':')[-1]
                        ts_key = f"device:{device_id}:temp"

                        alert_data = None
                        if temperature > MAX_TEMP:
                            alert_data = {'device_id': device_id, 'type': 'high_temp', 'temp_reading': temperature, 'threshold': MAX_TEMP, 'timestamp': timestamp_ms}
                        elif temperature < MIN_TEMP:
                            alert_data = {'device_id': device_id, 'type': 'low_temp', 'temp_reading': temperature, 'threshold': MIN_TEMP, 'timestamp': timestamp_ms}
                        
                        if alert_data:
                            r.xadd(ANOMALY_ALERTS_STREAM, alert_data)
                            print(f"*** ANOMALY DETECTED! *** Published alert to '{ANOMALY_ALERTS_STREAM}': {alert_data}")

                        ts_client.add(ts_key, timestamp_ms, temperature,
                                      retention_msecs=2592000000,
                                      labels={'unit': 'celsius', 'device': device_id}
                                     )
                        
                        r.xack(INPUT_STREAM_KEY, CONSUMER_GROUP_NAME, message_id)
                        print(f"RECOVERY: Acknowledged message ID: {message_id}")
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
                    print(f"DEBUG: Started processing message ID: {message_id}")
                    try:
                        decoded_data = {k: v for k, v in message_data_bytes.items()}
                        timestamp_ms = int(float(decoded_data.get('timestamp')) * 1000)
                        temperature = float(decoded_data.get('temperature_c'))
                        device_id = INPUT_STREAM_KEY.split(':')[-1]
                        ts_key = f"device:{device_id}:temp"

                        alert_data = None
                        if temperature > MAX_TEMP:
                            alert_data = {'device_id': device_id, 'type': 'high_temp', 'temp_reading': temperature, 'threshold': MAX_TEMP, 'timestamp': timestamp_ms}
                        elif temperature < MIN_TEMP:
                            alert_data = {'device_id': device_id, 'type': 'low_temp', 'temp_reading': temperature, 'threshold': MIN_TEMP, 'timestamp': timestamp_ms}
                        
                        if alert_data:
                            r.xadd(ANOMALY_ALERTS_STREAM, alert_data)
                            print(f"*** ANOMALY DETECTED! *** Published alert to '{ANOMALY_ALERTS_STREAM}': {alert_data}")

                        ts_client.add(ts_key, timestamp_ms, temperature,
                                      retention_msecs=2592000000,
                                      labels={'unit': 'celsius', 'device': device_id}
                                     )
                        
                        r.xack(INPUT_STREAM_KEY, CONSUMER_GROUP_NAME, message_id)
                        print(f"DEBUG: Finished processing and acknowledged message ID: {message_id}")

                    except Exception as ex:
                        print(f"CRITICAL ERROR: Failed to process message {message_id}. Reason: {ex}")
                        
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
