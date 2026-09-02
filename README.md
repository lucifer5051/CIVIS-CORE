# CIVIS-CORE

> **Cognitive Intelligent Video Intelligence and Surveillance System** — a modular, high-performance multi-camera computer vision platform for real-time video ingestion, object detection, tracking, identity analysis, and event intelligence.

---

## 🌟 Overview

**CIVIS-CORE** provides a clean, modular foundation for enterprise-grade video intelligence. Built with concurrency, resilience, and decoupled data pipelines at its core, CIVIS supports multi-source camera streams and AI inference engines out of the box.

```
       +-------------------------+
       |   Video / RTSP / File   |
       +------------+------------+
                    |
                    v
       +------------+------------+
       |   Ingestion Engine      |  ==> Standardized FramePacket
       +------------+------------+
                    |
                    v
       +------------+------------+
       |   Detection Engine      |  ==> Standardized DetectionResult
       |   (YOLO12 / Ultralytics)|
       +------------+------------+
                    |
                    v
       +------------+------------+
       |   SAHI & Tracking       |  (Upcoming Modules)
       +-------------------------+
```

---

       |   SAHI & Tracking       |
       |   Re-ID & Risk Engine   |
       |   Evidence & Custody    |
       +-------------------------+
                    |
                    v
       +------------+------------+
       |   FastAPI Backend       |  ==> REST / WebSocket
       |   React Dashboard       |  ==> Live operator console
       +-------------------------+
```

---

## 🚀 Quick Start — Any Laptop, Cold Boot

CIVIS-CORE ships with smart launcher scripts that work **on any Windows machine**, even on the very first run with no PATH configured.

### ▶️ Start

Double-click **`START_CIVIS.bat`** or run it from any terminal:

```
START_CIVIS.bat
```

The launcher will automatically:

| Step | What it does |
|------|-------------|
| **0** | Kill any stale processes on port 8000 |
| **1** | Find Python — checks PATH, `py` launcher, then 18+ common install dirs, Conda/Miniconda |
| **2** | Locate pip — bootstraps it via `ensurepip` if missing |
| **3** | Install from `requirements.txt` — **skips packages already installed** |
| **4** | Build React dashboard — only if `dist/` is missing; skips `npm install` if `node_modules/` exists |
| **5** | Report GPU / CUDA status |
| **6** | Launch backend + webcam pipeline and open browser |

### ⏹️ Stop

Double-click **`STOP_CIVIS.bat`** or run:

```
STOP_CIVIS.bat
```

Cleanly kills only CIVIS-related Python/uvicorn processes. Does **not** affect other Python apps running on your machine.

---

## 📶 Offline Support

| Scenario | Works offline? |
|----------|---------------|
| First run on a new laptop | ❌ Needs internet (pip + npm downloads) |
| Second run on the same machine | ✅ Fully offline |
| Moved to new PC with packages pre-installed | ✅ Fully offline |
| Moved to new PC, no packages installed | ❌ Needs internet for first setup |

> **pip is smart** — it checks installed packages and skips downloads when already satisfied. After first setup, verification takes ~2 seconds even without internet.

---

## 🛠️ Manual Installation (Optional)

If you prefer not to use the launcher scripts:

```bash
# Clone the repository
git clone https://github.com/lucifer5051/CIVIS-CORE.git
cd CIVIS-CORE

# Install Python dependencies
pip install -r requirements.txt

# Build the frontend (requires Node.js)
cd frontend/civis-dashboard
npm install
npm run build
cd ../..

# Start the server
python run_civis.py --camera 0 --port 8000 --host 0.0.0.0
```

---

## 🔗 Endpoints

Once running, open:

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | Operator dashboard |
| `http://localhost:8000/cameras/CAM_01/stream` | Live MJPEG stream |
| `ws://localhost:8000/ws/events` | WebSocket event feed |
| `http://localhost:8000/docs` | Interactive API docs (Swagger) |

---

## 🚀 Key Modules & Architecture

### 1. Camera & Video Ingestion (`civis.ingestion`)
- **Unified Abstraction (`VideoSource`)**: Transparent interface for webcams, local video files (`.mp4`, `.avi`), and RTSP network streams.
- **Thread-Bound Safety**: Dedicated background worker threads so OpenCV calls never block the control loop.
- **Resilient Reconnection**: Automatic state transitions (`CONNECTING → RUNNING → RECONNECTING → DISCONNECTED`) with exponential backoff.
- **Buffer & Lag Control**: Latest-Frame Buffer (queue size = 1) eliminates latency on live streams; file streams preserve full sequences.
- **Multi-Camera Manager (`StreamManager`)**: Concurrent registry for managing multiple streams simultaneously.

### 2. YOLO12 Detection Engine (`civis.detection`)
- **Direct `FramePacket` Consumption**: Zero-copy frame objects straight from ingestion.
- **Standardized Payload (`DetectionResult`)**: Bounding boxes, class IDs, confidence scores, camera/frame IDs, and inference timing.
- **Hardware Agnostic**: Auto-detects CUDA GPU with CPU fallback.
- **Mock Detector**: Deterministic engine for fast offline unit testing without model weights.

### 3. Re-ID & Tracking (`civis.reid`, `civis.tracking`)
- Multi-camera person re-identification across non-overlapping camera zones.
- Persistent track IDs with appearance feature matching.

### 4. Evidence & Chain of Custody (`civis.evidence`)
- Tamper-evident evidence packaging with cryptographic hashing.
- Full chain-of-custody metadata for forensic export.

### 5. Risk & Event Intelligence (`civis.risk`)
- Rule-based and ML-assisted threat scoring.
- Real-time alert generation with configurable severity levels.

### 6. Observability (`civis.observability`)
- Structured JSON logging with per-component trace IDs.
- Prometheus-compatible metrics endpoint.

---

## 🧪 Running Tests & Demos

```bash
# Automated test suite
python -m unittest discover tests

# Individual demos
python demo_ingestion.py          # Multi-camera ingestion
python demo_detection.py          # End-to-end YOLO detection
python demo_webcam.py             # Webcam live pipeline
python demo_reid_multicam.py      # Multi-camera Re-ID
python demo_evidence.py           # Evidence packaging
python demo_risk.py               # Risk scoring engine
python demo_dashboard.py          # Dashboard integration
```

---

## 📁 Repository Structure

```
CIVIS-CORE/
├── START_CIVIS.bat            # Cold-start launcher (any laptop, auto-installs)
├── STOP_CIVIS.bat             # Clean stop script
├── run_civis.py               # Main server entry point
├── requirements.txt           # Python dependencies
│
├── civis/
│   ├── ingestion/             # Camera & Video Ingestion Subsystem
│   │   ├── models.py          # CameraConfig, CameraStatus, FramePacket
│   │   ├── base.py            # VideoSource Abstract Class
│   │   ├── opencv_source.py   # Unified OpenCV Ingestion Engine
│   │   ├── stream_manager.py  # Multi-camera Manager
│   │   └── factory.py         # Source Factory
│   │
│   ├── detection/             # Object Detection Subsystem
│   │   ├── models.py          # BoundingBox, Detection, DetectionResult
│   │   ├── base.py            # BaseDetector Abstract Class
│   │   ├── yolo_detector.py   # YOLO12 / Ultralytics Engine
│   │   ├── mock_detector.py   # Mock Engine for Testing
│   │   └── factory.py         # Detector Factory
│   │
│   ├── reid/                  # Person Re-Identification
│   ├── tracking/              # Multi-object Tracking
│   ├── evidence/              # Chain-of-Custody & Evidence
│   ├── risk/                  # Risk & Event Intelligence
│   └── observability/         # Logging & Metrics
│
├── frontend/
│   └── civis-dashboard/       # React operator console (Vite + TypeScript)
│       └── dist/              # Built dashboard (served by FastAPI)
│
├── tests/                     # Unit Test Suite
├── models/                    # YOLO model weights (.pt files)
├── demo_*.py                  # Individual module demos
└── README.md
```

---

## ⚙️ Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | Auto-detected by launcher |
| pip | any | Auto-bootstrapped if missing |
| Node.js | 18+ | Only needed if frontend not yet built |
| CUDA (optional) | 11.8+ | Falls back to CPU automatically |

Python packages installed from `requirements.txt`:
- `opencv-python`, `numpy` — frame processing
- `ultralytics`, `torch` — YOLO inference
- `sahi`, `supervision` — tiling & tracking
- `fastapi`, `uvicorn`, `websockets`, `httpx` — API server
- `pydantic` — data validation

---

## 📄 License

This project is licensed under the MIT License.
