# AegisEdge: Industrial Vision AI & Safety Compliance Dashboard

An industrial-grade Edge AI safety and quality inspection dashboard for **Raspberry Pi 5** and edge vision sensors (including **Arducam UC-844**), running real-time YOLOv8 PPE detection with live telemetry, sub-second latency analytics, adjustable thresholds, safety compliance validation (PASS/FAIL), and inspection audit history.

---

## Key Features

- **Industrial Edge Architecture**:
  - Optimized for **Raspberry Pi 5** host and **Arducam UC-844** camera sensor.
  - Multi-threaded asynchronous video and inference pipeline with real-time FPS regulation.
  - Dual stream modes: **Live Camera** (OpenCV V4L2/DSHOW) and **Simulated Factory Stream** (dynamic multi-station scenarios).

- **Real-Time Live Dashboard**:
  - Live video stream HUD with high-contrast tactical bounding boxes and status ribbons.
  - Sub-millisecond latency tracking broken down by **Preprocess**, **Inference**, and **Postprocess** time.
  - Dynamic FPS counter, frame drop detection, and session runtime clock.

- **Dynamic Threshold & Pipeline Control**:
  - Interactive **Confidence Threshold Slider** (10% to 95%).
  - Interactive **IoU / NMS Threshold Slider** (20% to 80%).
  - Multi-resolution inference selector (320x320 ultra-fast, 480x480 balanced, 640x640 high precision).
  - Configurable Safety Inspection Policies:
    - *Standard Policy*: Hardhat required (bare head detection triggers immediate **FAIL**).
    - *Strict Policy*: Hardhat + protective gloves required.

- **Safety Compliance (PASS / FAIL) & Analytics**:
  - Instant visual and acoustic alerting (industrial audio alarm synthesizer on safety violation).
  - Yield statistics: Overall Pass Rate %, Total Passed, Total Failed.
  - Real-time rolling latency line chart (Chart.js) and detection mix doughnut chart.
  - Edge hardware telemetry: CPU load meter, RAM usage, and engine status.

- **Inspection Audit History (10 to 20 Records)**:
  - Rolling log of the last 20 inspection cycles with timestamps, detection breakdowns, confidence, latency, and status pills.
  - Clickable snapshot thumbnails with zoom modal viewer and download option.
  - Filter by *All*, *Pass Only*, or *Fail (Violations) Only*.
  - **One-click CSV Audit Log Export**.

- **Raspberry Pi 5 Hardware 3-LED Stack Light Control**:
  - Live hardware GPIO switching via `gpiozero` & `lgpio` on Raspberry Pi 5 RP1 chip:
    - **Yellow LED ON** (Pin 11 / GPIO 17): Gloves only identified.
    - **Green LED ON** (Pin 13 / GPIO 27): Helmet only identified.
    - **Red LED ON** (Pin 15 / GPIO 22): Both helmet and gloves identified.
    - **Common Ground** (Pin 14 / GND via 220&Omega; current-limiting resistor).
  - Synchronized live visual indicators displayed directly in the web dashboard and on the video HUD.
  - Automatic simulated fallback for smooth cross-platform testing on non-Pi systems.

- **Manual Snapshot & Image Inspection**:
  - Snapshot button to save timestamped high-resolution evidence to `snapshots/`.
  - Manual image uploader to test custom files against active model and thresholds.

---

## Hardware Profile

| Component | Specification |
|---|---|
| Host Gateway | Raspberry Pi 5 (Quad-core Arm Cortex-A76 @ 2.4GHz) |
| Camera Sensor | Arducam UC-844 (OpenCV VideoCapture backend) |
| Inference Engine | YOLOv8 (`best.pt`) - Helmet, Gloves, Head |
| Operating System | Raspberry Pi OS / Linux / Windows 11 |

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Launch Dashboard Server

On Windows:
```cmd
run_dashboard.bat
```
Or directly via Python:
```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

On Raspberry Pi / Linux:
```bash
chmod +x run_dashboard.sh
./run_dashboard.sh
```

### 3. Open in Browser

Open your browser and navigate to:
```
http://localhost:8000
```
or access remotely over the local edge network:
```
http://<RASPBERRY_PI_IP>:8000
```

---

## API Endpoints

- `GET /api/video_feed`: Low-latency MJPEG video feed with industrial HUD annotations.
- `WebSocket /ws/telemetry`: High-frequency real-time telemetry stream (latency, fps, counts, pass/fail, CPU, RAM).
- `GET /api/telemetry`: Polling fallback for system telemetry.
- `GET /api/history`: Retrieve the last 20 inspection events.
- `POST /api/history/clear`: Reset history buffer and counters.
- `GET /api/config`: Get current threshold, rule, and camera configurations.
- `POST /api/config`: Dynamically update thresholds, rules, resolution, or sources.
- `POST /api/snapshot`: Save and retrieve an annotated frame snapshot.
- `POST /api/test_upload`: Upload and immediately inspect an image file.
- `GET /api/system_info`: Edge host and hardware telemetry.
