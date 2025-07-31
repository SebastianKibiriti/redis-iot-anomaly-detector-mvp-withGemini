import redis
import json
import time

# --- Configuration ---
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
INPUT_STREAM_KEY = 'sensor:temperature:01' # The stream our producer sends to
CONSUMER_GROUP_NAME = 'anomaly_detector_group'
CONSUMER_NAME = 'processor-01' # Unique name for this consumer instance

# --- Redis Connection ---
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    ts_client = r.ts() # Get the TimeSeries client object from the main Redis client
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
    Reads messages from the stream using a consumer group,
    stores relevant data in Redis Time Series, and acknowledges messages.
    """
    print(f"Starting consumer '{CONSUMER_NAME}' in group '{CONSUMER_GROUP_NAME}' for stream '{INPUT_STREAM_KEY}'...")
    
    while True:
        try:
            # Read messages from the stream.
            # count=1: Read one message at a time. Adjust for batch processing.
            # block=1000: Block for 1000ms if no new messages.
            # streams: A dictionary mapping stream names to IDs. '>' means new unread messages.
            messages = r.xreadgroup(
                groupname=CONSUMER_GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={INPUT_STREAM_KEY: '>'},
                count=1,
                block=1000
            )

            if not messages:
                # print("No new messages. Waiting...")
                time.sleep(0.1) # Small sleep to prevent busy-waiting if block doesn't work perfectly or you use block=0
                continue

            for stream_name, stream_messages in messages:
                for message_id, message_data_bytes in stream_messages:
                    # Redis returns data as bytes, decode to string and then parse JSON
                    try:
                        # message_data_bytes is a dictionary of bytes, convert values to string
                        decoded_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in message_data_bytes.items()}
                        
                        # Assuming the producer sends JSON string for complex data or just simple fields
                        # If producer.py sends simple fields directly, no json.loads needed
                        # For our producer.py, it sends dictionary, so decoded_data is already parsed
                        
                        # Extract relevant fields
                        timestamp_ms = int(float(decoded_data.get('timestamp')) * 1000) # Convert Unix timestamp (float) to milliseconds (int)
                        temperature = float(decoded_data.get('temperature_c'))
                        
                        # For simplicity, let's assume 'device_id' for now, but in our producer, we don't have it.
                        # Let's hardcode a device_id or extract it from stream name.
                        # For this example, let's create a dynamic TS key based on STREAM_KEY for simplicity
                        # In a real scenario, producer should send device_id
                        device_id = INPUT_STREAM_KEY.split(':')[-1] # Extracts '01' from 'sensor:temperature:01'
                        
                        # Define the Time Series key for this specific device's temperature
                        ts_key = f"device:{device_id}:temp"
                        
                        # TS.ADD command: Adds a sample to a Time Series.
                        # We use '*' for timestamp to let Redis set it (it will use current server time in ms)
                        # Or, we use the timestamp from the incoming message if it's reliable and unique enough.
                        # Using incoming timestamp is better for data integrity.
                        # We'll use the timestamp from the message, converted to milliseconds
                        ts_client.add(ts_key, timestamp_ms, temperature,
                                      # Optional: Create the Time Series if it doesn't exist
                                      # with specific retention or labels.
                                      # Here, we set retention to ~30 days (2592000000 ms) and add a label.
                                      # This is only applied if the TS is being created for the first time.
                                      # Make sure TS.CREATE / TS.ADD params are consistent if reusing keys.
                                      retention_msecs=2592000000, # 30 days retention
                                      labels={'unit': 'celsius', 'device': device_id}
                                     )
                        
                        print(f"Processed message {message_id} from stream '{INPUT_STREAM_KEY}': "
                              f"Stored temperature {temperature}°C for {device_id} in TS '{ts_key}'.")
                        
                        # Acknowledge the message to remove it from the Pending Entries List (PEL)
                        r.xack(INPUT_STREAM_KEY, CONSUMER_GROUP_NAME, message_id)
                        
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON from message {message_id}. Data: {message_data_bytes}")
                        # You might want to NACK or move to a dead-letter queue here
                    except ValueError as ve:
                        print(f"Data conversion error for message {message_id}: {ve}. Data: {decoded_data}")
                        # Again, handle malformed data
                    except Exception as ex:
                        print(f"An unexpected error occurred processing message {message_id}: {ex}")
                        # General error, log and potentially retry or dead-letter
                        
        except redis.exceptions.ConnectionError as e:
            print(f"Lost connection to Redis. Retrying in 5 seconds... Error: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nProcessor stopped by user.")
            break
        except Exception as e:
            print(f"An unhandled error occurred in the main loop: {e}")
            time.sleep(1) # Prevent tight loop on persistent error

if __name__ == "__main__":
    create_consumer_group()
    process_messages()
