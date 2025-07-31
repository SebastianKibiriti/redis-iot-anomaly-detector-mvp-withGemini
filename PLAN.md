# Redis Anomaly Detection MVP - 11-Day Sprint Plan

**Project Goal:** Real-time Temperature Anomaly Detection for Data Center Server Racks.
**MVP Focus:** Simple fixed threshold breaches for temperature (sudden spikes/drops).
**Alerting:** Console logs.
**Due Date:** Sunday, August 10, 2025

---

## Phase 1: Foundation & Ingestion (Days 1-3)

### Day 1 (Jul 31, Thu): Redis Setup & Basic Connection
- [ ] **08:30 - 10:00:** **Redis Stack Installation via Docker Compose.**
    - Create `docker-compose.yml` (see below for content).
    - Run `docker compose up -d`.
- [ ] **10:00 - 12:00:** **Python Environment Setup.**
    - Create virtual environment: `python -m venv venv`.
    - Activate: `source venv/bin/activate` (Linux/macOS) or `.\venv\Scripts\activate` (Windows PowerShell).
    - Install `redis-py`: `pip install redis`.
- [ ] **12:00 - 13:00:** Lunch Break
- [ ] **13:00 - 15:00:** **Basic Redis Connectivity Test (Python).**
    - Write a short script (`test_redis_connection.py`) to `PING` Redis, `SET` a key, and `GET` it back.
- [ ] **15:00 - 17:00:** **Redis TS/Stream Initialization Test (Python).**
    - Define `device_id` naming (e.g., `inrow-ABC-1`).
    - Define stream (`raw_sensor_data`) and TS key pattern (`sensor:<device_id>:temp`).
    - Write script to `TS.CREATE` a dummy Time Series and `TS.ADD` a single data point to verify Time Series module.

### Day 2 (Aug 01, Fri): Data Generator & Stream Ingestion
- [ ] **09:00 - 12:00:** **Data Generator Script (`data_generator.py`).**
    - Simulate 5-10 sensors.
    - Generate realistic temperature data (e.g., 20-25°C with fluctuations, occasionally introduce anomalies later).
    - Add data to `raw_sensor_data` Redis Stream using `XADD`.
    - Set frequency (e.g., 1 data point/second/sensor).
- [ ] **12:00 - 13:00:** Lunch Break
- [ ] **13:00 - 17:00:** **Test Data Generator & Redis Insight.**
    - Run `data_generator.py`.
    - Verify data accumulation in `raw_sensor_data` stream using `redis-cli` (`XREAD COUNT 10 STREAMS raw_sensor_data 0`) or Redis Insight.

### Day 3 (Aug 02, Sat): Stream Processing & Time Series Storage
- [ ] **09:00 - 12:00:** **Stream Processor Script - Part 1 (`stream_processor.py`).**
    - Implement Redis Stream Consumer Group for `raw_sensor_data` (e.g., `anomaly_detector_group`).
    - Use `XGROUP CREATE` and `XREADGROUP`.
    - Parse `device_id`, `temperature`, `timestamp` from messages.
    - Use `TS.ADD` to store data in `sensor:<device_id>:temp`.
    - Implement `XACK` after processing messages.
- [ ] **12:00 - 13:00:** Lunch Break
- [ ] **13:00 - 17:00:** **Test Stream Processor.**
    - Run `data_generator.py` and `stream_processor.py` simultaneously.
    - Verify data written to individual Time Series keys using `redis-cli` (`TS.RANGE sensor:inrow-ABC-1:temp - +`) or Redis Insight.
    - Add basic error handling for message parsing.

---

## Phase 2: Anomaly Detection & Alerting (Days 4-7)

### Day 4 (Aug 03, Sun): Threshold-Based Anomaly Detection Logic
- [ ] **09:00 - 12:00:** **Anomaly Detection Logic in `stream_processor.py`.**
    - Define `MIN_TEMP` (e.g., 18°C) and `MAX_TEMP` (e.g., 28°C) constants.
    - Check if `temperature` is `< MIN_TEMP` or `> MAX_TEMP`.
    - If anomalous, add a descriptive message to the `anomaly_alerts` Redis Stream.
        - Message format: `{'type': 'high_temp'/'low_temp', 'device_id': ..., 'temperature': ..., 'timestamp': ..., 'threshold': ...}`
- [ ] **12:00 - 13:00:** Lunch Break
- [ ] **13:00 - 17:00:** **Test Anomaly Detection.**
    - Modify `data_generator.py` to occasionally generate anomalous readings.
    - Run generator and processor. Verify anomalies appear in `anomaly_alerts` stream.

### Day 5 (Aug 04, Mon): Alert Consumer & Consolidation
- [ ] **09:00 - 12:00:** **Alert Consumer Script (`alert_consumer.py`).**
    - Create Redis Stream Consumer Group for `anomaly_alerts` (e.g., `alert_logger_group`).
    - Read messages from `anomaly_alerts` stream.
    - Parse and print human-readable alerts to console.
    - Remember `XACK`.
- [ ] **12:00 - 13:00:** Lunch Break
- [ ] **13:00 - 17:00:** **End-to-End Test.**
    - Run all three components (`data_generator.py`, `stream_processor.py`, `alert_consumer.py`).
    - Ensure simulated anomalies trigger console alerts. Review logs.

### Day 6 (Aug 05, Tue): Basic Dashboard (Optional Stretch) / Refinement
- [ ] **09:00 - 13:00:** **Optional: Basic Web Dashboard (Flask/Dash).**
    - Set up minimal Flask/Dash app. Read latest N alerts from `anomaly_alerts` or consume new ones. Display in simple HTML.
    - **OR** Enhanced Console/File Logging: Add timestamps, details to console alerts. Implement logging to file using Python's `logging` module.
- [ ] **13:00 - 14:00:** Lunch Break
- [ ] **14:00 - 17:00:** **Refinement & Minor Improvements.**
    - Add comments to code.
    - Refactor repeated code.
    - Ensure graceful shutdowns (Ctrl+C).
    - Add meaningful `print()` statements for debugging.

### Day 7 (Aug 06, Wed): Robustness Testing & Edge Cases
- [ ] **09:00 - 12:00:** **Stress Testing.**
    - Increase simulated sensors, data frequency, and anomaly bursts.
    - Monitor Redis CPU/memory usage (`redis-cli info stats` or Redis Insight).
- [ ] **12:00 - 13:00:** Lunch Break
- [ ] **13:00 - 17:00:** **Failure Scenarios & Recovery.**
    - Stop/start `stream_processor.py` midway. Verify resume from correct offset.
    - Simulate data generator outage.
    - Check for unacknowledged messages (`XPENDING`).
    - Ensure `XACK` is correct.

---

## Phase 3: Testing & Submission (Days 8-11)

### Day 8 (Aug 07, Thu): Code Review & Documentation
- [ ] **09:00 - 12:00:** **Code Review & Refactoring.**
    - Clean up codebase, clear variable names, well-defined functions.
    - Add docstrings. Use environment variables/config for hardcoded values.
- [ ] **12:00 - 13:00:** Lunch Break
- [ ] **13:00 - 17:00:** **Initial `README.md` Draft.**
    - Purpose, architecture, Redis usage.
    - Clear setup instructions (Docker Compose, Python deps).
    - How to run each component.
    - Highlight Redis 8 features (Time Series, Streams).

### Day 9 (Aug 08, Fri): Video Script & Demo Preparation
- [ ] **09:00 - 12:00:** **Demo Scripting.**
    - Write clear, concise script for demo video.
    - What to show (start generator, Redis Insight, trigger anomaly, console alert, dashboard if built).
    - Highlight real-time aspect & Redis features.
- [ ] **12:00 - 13:00:** Lunch Break
- [ ] **13:00 - 17:00:** **Demo Dry Run & Practice.**
    - Do a dry run. Identify rough edges.
    - Practice speaking points.
    - Ensure reliable component startup.

### Day 10 (Aug 09, Sat): Final Polish & Submission Package
- [ ] **09:00 - 13:00:** **Record Demo Video.**
    - Record following script. Aim for clarity.
    - Use screen recording software (OBS Studio, Loom).
    - Edit if necessary.
- [ ] **13:00 - 14:00:** Lunch Break
- [ ] **14:00 - 17:00:** **Finalize Documentation & Submission.**
    - Review `README.md` one last time.
    - Create `requirements.txt` (`pip freeze > requirements.txt`).
    - Organize GitHub repository.
    - Double-check all required files present.

### Day 11 (Aug 10, Sun): Submission Day!
- [ ] **09:00 - 12:00:** **Final Checks & Submission.**
    - Review challenge submission guidelines.
    - Ensure all links (GitHub repo, video) work.
    - Write submission text.
- [ ] **12:00 onwards:** CELEBRATE!