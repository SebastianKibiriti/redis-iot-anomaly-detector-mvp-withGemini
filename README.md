# Redis-Powered IoT Anomaly Detector

This project demonstrates a robust, real-time data processing pipeline for an Internet of Things (IoT) sensor using Redis Streams and Redis Time Series. It's designed to ingest a stream of sensor data, detect anomalies, store the data efficiently for historical analysis, and alert a separate service to critical events—all in real time.

## Architecture

The system is built on a a microservices architecture, with each component performing a single, well-defined function. Redis serves as the central hub for all data communication and storage, providing a durable, high-performance foundation.

The data flow is as follows:

```text
+-----------------+     +--------------------------+     +--------------------+
| producer.py     | --> | Redis Stream (raw_data)  | --> | stream_processor.py|
| (data generator)|     |                          |     |                    |
+-----------------+     +--------------------------+     +--------------------+
                                  |         ^
                                  |         |
                          +-------v---------+         +------------------+
                          | Redis TimeSeries| <-----> | dashboard.py     |
                          | (archived data) |         | (web dashboard)  |
                          +-----------------+         +------------------+
                                  |
                                  | (anomalies)
                                  V
                          +--------------------------+
                          | Redis Stream (alerts)    |
                          |                          |
                          +--------------------------+
                                  |
                                  V
                          +--------------------+
                          | alert_consumer.py  |
                          | (logs alerts)      |
                          +--------------------+
```

## Features

*   **Real-time Data Ingestion**: Uses Redis Streams as a durable message queue for a continuous flow of sensor data.
*   **Robust Stream Processing**: The `stream_processor` uses Redis Consumer Groups to ensure no data is lost, even if the processor crashes and restarts.
*   **Anomaly Detection**: A simple, threshold-based logic in the `stream_processor` identifies and flags anomalous temperature readings.
*   **Decoupled Alerting System**: Anomalies are published to a separate Redis Stream, allowing an independent `alert_consumer` to process them.
*   **Time-Series Data Archiving**: The raw sensor data is stored in Redis Time Series keys for efficient historical analysis and visualization.
*   **Live Dashboard**: A simple web-based dashboard provides a live, interactive view of the sensor's temperature data.

## Getting Started

### Prerequisites

*   **Docker and Docker Compose**: To run the Redis Stack server.
*   **Python 3.8+**: The runtime environment for all scripts.
*   **pip**: Python's package installer.

### Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/sebastiankibiriti/redis-iot-anomaly-detector-mvp-withGemini.git
    cd redis-iot-anomaly-detector-mvp-withGemini
    ```
2.  **Start Redis with Docker Compose:**
    ```bash
    docker compose up -d
    ```
    This will start a Redis Stack container and expose the necessary ports.

3.  **Create a Python Virtual Environment:**
    ```bash
    python -m venv venv
    # On Windows (PowerShell)
    .\venv\Scripts\activate.ps1
    # On macOS/Linux
    source venv/bin/activate
    ```
4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## How to Run the Application

The application consists of four independent scripts that must be run concurrently in four separate terminals.

**Terminal 1: Data Producer**
```bash
python producer.py
```

**Terminal 2: Stream Processor**
```bash
python stream_processor.py
```

**Terminal 3: Alert Consumer**
```bash
python alert_consumer.py
```

**Terminal 4: Web Dashboard**
```bash
python dashboard.py
```

Once the dashboard is running, you can access it at `http://127.0.0.1:8050/` in your web browser.