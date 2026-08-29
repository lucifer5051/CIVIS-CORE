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

## 🚀 Key Modules & Architecture

### 1. Camera & Video Ingestion (`civis.ingestion`)
- **Unified Abstraction (`VideoSource`)**: Transparent interface for local video files (`.mp4`, `.avi`), webcams, and network RTSP streams.
- **Thread-Bound Safety**: Dedicated background worker threads ensuring OpenCV `VideoCapture` calls (`open`, `read`, `release`) never block or crash the control loop.
- **Resilient Reconnection**: Automatic state transitions (`CONNECTING`, `RUNNING`, `RECONNECTING`, `DISCONNECTED`, `ERROR`) and exponential backoff retry for network streams.
- **Buffer & Lag Control**: Real-time streams enforce a **Latest-Frame Buffer** policy (queue size = 1) to eliminate video latency, while file streams preserve full frame sequences.
- **Multi-Camera Manager (`StreamManager`)**: Concurrent registry for managing multiple streams simultaneously.

### 2. YOLO12 Detection Engine (`civis.detection`)
- **Direct `FramePacket` Consumption**: Consumes standard zero-copy frame objects directly from the ingestion module.
- **Standardized Payload (`DetectionResult`)**: Encapsulates bounding boxes (`x1, y1, x2, y2`), class IDs, label names, confidence scores, camera/frame identifiers, and inference timing metrics.
- **Hardware Agnostic**: Automatic CPU/CUDA GPU hardware detection with fallback mechanics.
- **Mock Detector (`MockDetector`)**: Deterministic engine for fast offline unit testing without downloading model weights.

---

## 🛠️ Installation & Setup

```bash
# Clone the repository
git clone https://github.com/lucifer5051/CIVIS-CORE.git
cd CIVIS-CORE

# Install dependencies
pip install -r requirements.txt
```

---

## 🧪 Running Tests & Demos

### 1. Run Automated Test Suite
```bash
python -m unittest discover tests
```

### 2. Run Ingestion Stream Demo
```bash
python demo_ingestion.py
```

### 3. Run End-to-End Detection Engine Demo
```bash
python demo_detection.py
```

---

## 📁 Repository Structure

```
CIVIS-CORE/
├── civis/
│   ├── ingestion/             # Camera & Video Ingestion Subsystem
│   │   ├── models.py          # CameraConfig, CameraStatus, FramePacket
│   │   ├── base.py            # VideoSource Abstract Class
│   │   ├── opencv_source.py   # Unified OpenCV Ingestion Engine
│   │   ├── stream_manager.py  # Multi-camera Manager
│   │   └── factory.py         # Source Factory
│   │
│   └── detection/             # Object Detection Subsystem
│       ├── models.py          # BoundingBox, Detection, DetectionResult
│       ├── base.py            # BaseDetector Abstract Class
│       ├── yolo_detector.py    # YOLO12 / Ultralytics Engine
│       ├── mock_detector.py    # Mock Engine for Testing
│       └── factory.py         # Detector Factory
│
├── tests/                     # Unit Test Suite
│   ├── test_ingestion.py
│   └── test_detection.py
│
├── demo_ingestion.py          # Multi-camera Ingestion Demo
├── demo_detection.py          # End-to-End Detection Pipeline Demo
├── requirements.txt           # Project Dependencies
└── README.md                  # System Documentation
```

---

## 📄 License
This project is licensed under the MIT License.
