import redis
import time
import json

# --- Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
ALERT_STREAM_KEY = 'anomaly_alerts'
CONSUMER_GROUP_NAME = 'alert_logger_group'
CONSUMER_NAME = 'alert_consumer_01'

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
    Creates the consumer group for the alert stream if it doesn't already exist.
    """
    try:
        r.xgroup_create(ALERT_STREAM_KEY, CONSUMER_GROUP_NAME, id='0', mkstream=True)
        print(f"Consumer group '{CONSUMER_GROUP_NAME}' created for stream '{ALERT_STREAM_KEY}'.")
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"Consumer group '{CONSUMER_GROUP_NAME}' already exists.")
        else:
            print(f"Error creating consumer group: {e}")
            exit(1)

def consume_alerts():
    """
    Consumes and logs anomaly alerts from the stream.
    """
    print(f"Starting alert consumer '{CONSUMER_NAME}' in group '{CONSUMER_GROUP_NAME}' for stream '{ALERT_STREAM_KEY}'...")
    
    while True:
        try:
            # Use XREADGROUP to get new alerts.
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
                for message_id, message_data_bytes in stream_messages:
                    try:
                        # Data is already decoded due to `decode_responses=True`
                        alert_data = {k: v for k, v in message_data_bytes.items()}
                        
                        # Print a human-readable alert message
                        print("--- NEW ANOMALY ALERT ---")
                        print(f"Alert ID: {message_id}")
                        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(alert_data['timestamp']) / 1000))}")
                        print(f"Device ID: {alert_data['device_id']}")
                        print(f"Type: {alert_data['type']}")
                        print(f"Temperature: {alert_data['temp_reading']}°C (Threshold: {alert_data['threshold']}°C)")
                        print("--------------------------")
                        
                        # Acknowledge the message to remove it from the Pending Entries List (PEL)
                        r.xack(ALERT_STREAM_KEY, CONSUMER_GROUP_NAME, message_id)
                        
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
    consume_alerts()
