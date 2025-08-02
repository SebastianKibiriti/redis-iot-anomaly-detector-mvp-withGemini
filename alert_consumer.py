import redis
import json
import time
from datetime import datetime

# --- Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
ALERT_STREAM_KEY = 'anomaly_alerts' # The stream where our processor publishes alerts
CONSUMER_GROUP_NAME = 'alert_consumer_group'
CONSUMER_NAME = 'alert_consumer-01'

# --- Redis Connection ---
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    if not r.ping():
        raise redis.exceptions.ConnectionError("Could not ping Redis server.")
    print("Successfully connected to Redis for alert consumption.")
except redis.exceptions.ConnectionError as e:
    print(f"ERROR: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Please ensure it's running.")
    print(f"Error details: {e}")
    exit(1)

def create_consumer_group():
    """
    Creates the consumer group for the alerts stream if it doesn't already exist.
    """
    try:
        # Create a new consumer group for the anomaly alerts stream
        r.xgroup_create(ALERT_STREAM_KEY, CONSUMER_GROUP_NAME, id='0', mkstream=True)
        print(f"Consumer group '{CONSUMER_GROUP_NAME}' created for stream '{ALERT_STREAM_KEY}'.")
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"Consumer group '{CONSUMER_GROUP_NAME}' already exists for stream '{ALERT_STREAM_KEY}'.")
        else:
            print(f"Error creating consumer group: {e}")
            exit(1)

def run_alert_consumer():
    """
    Reads new alert messages from the stream and prints them.
    """
    print(f"Starting alert consumer '{CONSUMER_NAME}' in group '{CONSUMER_GROUP_NAME}' for stream '{ALERT_STREAM_KEY}'...")
    
    # Check for pending messages to recover
    print("Checking for pending messages to recover...")
    while True:
        try:
            # We use '0' to read from the start of the PEL
            messages = r.xreadgroup(
                groupname=CONSUMER_GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={ALERT_STREAM_KEY: '0'},
                count=1,
                block=1000
            )

            if not messages or not messages[0][1]:
                print("No pending messages found. Starting live alert consumption.")
                break

            for stream_name, stream_messages in messages:
                for message_id, message_data in stream_messages:
                    try:
                        # Process and print the recovered message
                        print_alert(message_id, message_data)
                        
                        # Acknowledge the message
                        r.xack(ALERT_STREAM_KEY, CONSUMER_GROUP_NAME, message_id)
                    except Exception as ex:
                        print(f"CRITICAL ERROR (RECOVERY): Failed to process message {message_id}. Reason: {ex}")
        except redis.exceptions.ConnectionError as e:
            print(f"Lost connection to Redis during recovery. Retrying in 5 seconds... Error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"An unhandled error occurred in the recovery loop: {e}")
            time.sleep(1)

    # Main loop for new messages
    while True:
        try:
            # Read new messages using '>'
            messages = r.xreadgroup(
                groupname=CONSUMER_GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={ALERT_STREAM_KEY: '>'},
                count=1,
                block=1000
            )

            if not messages:
                time.sleep(0.1)
                continue

            for stream_name, stream_messages in messages:
                for message_id, message_data in stream_messages:
                    try:
                        print_alert(message_id, message_data)
                        r.xack(ALERT_STREAM_KEY, CONSUMER_GROUP_NAME, message_id)
                    except Exception as ex:
                        print(f"An unexpected error occurred processing message {message_id}: {ex}")

        except redis.exceptions.ConnectionError as e:
            print(f"Lost connection to Redis. Retrying in 5 seconds... Error: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nConsumer stopped by user.")
            break
        except Exception as e:
            print(f"An unhandled error occurred in the main loop: {e}")
            time.sleep(1)

def print_alert(message_id, message_data):
    """
    Formats and prints the alert data.
    """
    try:
        timestamp_ms = int(float(message_data.get('timestamp')))
        timestamp_dt = datetime.fromtimestamp(timestamp_ms / 1000.0)

        print("\n" + "-"*20 + " NEW ANOMALY ALERT " + "-"*20)
        print(f"Alert ID: {message_id}")
        print(f"Timestamp: {timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Device ID: {message_data.get('device_id')}")
        print(f"Type: {message_data.get('type')}")
        print(f"Temperature: {float(message_data.get('temp_reading')):.2f}°C")
        if message_data.get('moving_average'):
            print(f"Moving Average: {float(message_data.get('moving_average')):.2f}°C")
        if message_data.get('standard_deviation'):
            print(f"Standard Deviation: {float(message_data.get('standard_deviation')):.2f}°C")
        print("-" * 59)
    except Exception as e:
        print(f"Failed to decode or print alert message {message_id}: {e}")
        print(f"Raw data: {message_data}")

if __name__ == "__main__":
    create_consumer_group()
    run_alert_consumer()
