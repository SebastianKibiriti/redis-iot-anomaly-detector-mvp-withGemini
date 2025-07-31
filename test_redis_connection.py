import redis

# --- Configuration ---
# Your Redis server should be running on localhost:6379,
# as defined in the docker-compose.yml file.
REDIS_HOST = 'localhost'
REDIS_PORT = 6379

def test_redis_connection():
    """
    Attempts to connect to Redis, set a key, get the key, and print the result.
    """
    print("Attempting to connect to Redis...")
    try:
        # Create a Redis client instance
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        
        # Ping the server to check for connectivity
        if r.ping():
            print("Successfully connected to Redis!")
            
            # --- Perform a simple key-value operation ---
            key = "challenge:status"
            value = "connected"
            
            # Set a key
            r.set(key, value)
            print(f"Set key '{key}' with value '{value}'")
            
            # Get the key
            retrieved_value = r.get(key)
            print(f"Retrieved key '{key}': {retrieved_value}")
            
            # Check if the retrieved value is correct
            if retrieved_value == value:
                print("Test successful! Redis is working as expected.")
            else:
                print("Test failed: Retrieved value does not match the set value.")
            
        else:
            print("Failed to ping Redis server. Connection issues?")
            
    except redis.exceptions.ConnectionError as e:
        print(f"Connection Error: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
        print("Please ensure your Docker container is running.")
        print(f"Error details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_redis_connection()
