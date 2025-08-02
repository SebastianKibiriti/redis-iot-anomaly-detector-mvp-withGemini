import redis
import json
import time
from datetime import datetime

# --- Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
ANOMALY_ALERTS_STREAM = 'anomaly_alerts'
CONSUMER_GROUP_NAME = 'alert_consumer_group'
CONSUMER_NAME = 'alert_processor-01'

# --- Redis Connection ---
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    if not r.ping():
        raise redis.exceptions.ConnectionError("Could not ping Redis server.")
    print("Successfully connected to Redis for alert processing.")
except redis.exceptions.ConnectionError as e:
    print(f"ERROR: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Please ensure it's running.")
    print(f"Error details: {e}")
    exit(1)

def create_consumer_group():
    """
    Creates the consumer group if it doesn't already exist.
    """
    try:
        r.xgroup_create(ANOMALY_ALERTS_STREAM, CONSUMER_GROUP_NAME, id='0', mkstream=True)
        print(f"Consumer group '{CONSUMER_GROUP_NAME}' created for stream '{ANOMALY_ALERTS_STREAM}'.")
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"Consumer group '{CONSUMER_GROUP_NAME}' already exists.")
        else:
            print(f"Error creating consumer group: {e}")
            exit(1)

def process_alerts():
    """
    Listens for new alerts and prints them to the console.
    """
    print(f"Starting alert consumer '{CONSUMER_NAME}' for stream '{ANOMALY_ALERTS_STREAM}'...")
    while True:
        try:
            # Read from the stream, waiting for new messages (block=1000)
            messages = r.xreadgroup(
                groupname=CONSUMER_GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={ANOMALY_ALERTS_STREAM: '>'},
                count=1,
                block=1000
            )

            if not messages:
                continue

            for stream_name, stream_messages in messages:
                for message_id, message_data_bytes in stream_messages:
                    try:
                        alert = {k: v for k, v in message_data_bytes.items()}
                        
                        alert_type = alert.get('type')
                        timestamp_ms = int(alert.get('timestamp'))
                        timestamp = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')

                        print("\n--- NEW ANOMALY ALERT ---")
                        print(f"Alert ID: {message_id}")
                        print(f"Timestamp: {timestamp}")
                        print(f"Device ID: {alert.get('device_id')}")
                        print(f"Type: {alert_type}")
                        
                        # Handle both old and new alert formats
                        if alert_type in ['high_temp', 'low_temp']:
                            print(f"Temperature: {float(alert.get('temp_reading')):.2f}°C (Threshold: {float(alert.get('threshold')):.2f}°C)")
                        elif alert_type == 'statistical_anomaly':
                            print(f"Temperature: {float(alert.get('temp_reading')):.2f}°C")
                            print(f"Moving Average: {float(alert.get('moving_average')):.2f}°C")
                            print(f"Standard Deviation: {float(alert.get('standard_deviation')):.2f}°C")
                        
                        print("--------------------------")
                        
                        # Acknowledge the message
                        r.xack(ANOMALY_ALERTS_STREAM, CONSUMER_GROUP_NAME, message_id)
                    
                    except Exception as ex:
                        print(f"Error processing alert {message_id}: {ex}")
        
        except redis.exceptions.ConnectionError as e:
            print(f"Lost connection to Redis. Retrying in 5 seconds... Error: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nAlert consumer stopped by user.")
            break
        except Exception as e:
            print(f"An unhandled error occurred in the main loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    create_consumer_group()
    process_alerts()
