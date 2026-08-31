# CIVIS-CORE: Live Laptop Webcam & Web Operator Console

This guide explains how to run the CIVIS-CORE computer vision and surveillance analytics pipeline against a live local webcam, video file, or RTSP stream, and monitor it through either the **Live Web Operator Console** or the **Standalone OpenCV Window**.

---

## 1. Prerequisites & Dependencies

The system runs on the standard CIVIS-CORE environment:

```bash
# Core backend dependencies
pip install fastapi uvicorn opencv-python numpy pydantic

# Optional neural model backends (YOLO, SAHI, PyTorch)
pip install torch ultralytics sahi

# Frontend Dashboard (Vite + React + TypeScript)
cd frontend/civis-dashboard
npm install
npm run build
cd ../..
```

> **Note**: If neural weights or physical webcam hardware are not available in your environment, pass `--use-mock` or rely on the automatic synthetic fallback mode.

---

## 2. Quick Start: Browser Operator Console (Recommended)

Start the unified CIVIS-CORE backend with live webcam streaming and operator console:

```bash
# Start backend + live webcam and open browser console automatically
python run_civis.py --camera 0 --open-browser
```

### Access Points
- **Operator Console**: [http://localhost:8000](http://localhost:8000)
- **Live MJPEG Camera Stream**: [http://localhost:8000/cameras/CAM_01/stream](http://localhost:8000/cameras/CAM_01/stream)
- **Single JPEG Snapshot**: [http://localhost:8000/cameras/CAM_01/snapshot](http://localhost:8000/cameras/CAM_01/snapshot)
- **Real-Time Telemetry WebSocket**: `ws://localhost:8000/ws/events`
- **Interactive REST API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Lightweight / Low-Latency Stream (640x480, 15 FPS)
```bash
python run_civis.py --camera 0 --width 640 --height 480 --fps 15
```

### Frontend Hot-Reload Development Mode
```bash
# Terminal 1: Backend
python run_civis.py --camera 0

# Terminal 2: React Dashboard with Hot Module Replacement
cd frontend/civis-dashboard
npm run dev
```

---

## 3. Alternative: Standalone OpenCV Window

If you prefer a direct OpenCV desktop window without running the web server:

```bash
# Live webcam execution with OpenCV GUI
python demo_webcam.py --camera 0

# Adaptive SAHI small-object detection
python demo_webcam.py --sahi adaptive --face-detector yunet --conf 0.30

# Headless / deterministic test run
python demo_webcam.py --use-mock --no-display --max-frames 30
```

---

## 4. Web Console Architecture & Layout

The React Operator Console features a dedicated **Live Monitor** view:

### Top Navigation & Control Bar
- **System Status**: `HEALTHY` / `DEGRADED` / `OFFLINE` badge with pulse indicator.
- **Camera Feed Selector**: Dropdown to select active camera feed (`CAM_01`, `CAM_02`).
- **Camera State**: `LIVE STREAMING` (Green), `PAUSED` (Amber), `OFFLINE` (Slate).
- **Controls**: `[Start Camera]`, `[Stop Camera]`, `[Pause]`, `[Resume]`.
- **Privacy Assurance**: `🔒 LOCAL ONLY • ZERO CLOUD STORAGE • PRIVACY SAFE`.
- **Performance Chips**: Real-time Capture FPS, Pipeline Latency, Processed Frame Counter.

### Main Workspace (Split Grid)
- **Left Column (Large Video Feed)**:
  - Live multipart/x-mixed-replace MJPEG video stream.
  - Video status overlays: Live tag, top-right risk severity banner, and bottom track count badges.
  - Interactive placeholder and recovery if camera is offline.
- **Right Column (Live Intelligence Stream)**:
  - **Active Tracks**: List of current tracked objects with class names and confidence percentages.
  - **Face & Identity**: Detected faces, known names, and `UNKNOWN` status badges.
  - **Cross-Camera Re-ID**: Global entity IDs linked across multiple camera feeds.
  - **Behavior Observations**: Active loitering, dwelling, and zone boundary events.

### Bottom Telemetry & Scrolling Event Stream
- **Pipeline Stage Profiler (ms)**: Real-time per-stage latencies for `detection`, `tracking`, `identity`, `reid`, `behavior`, and `risk`.
- **Live Audit Event Stream**: Auto-scrolling WebSocket event timeline displaying incoming security events and state changes.

---

## 5. Command-Line Reference

### `run_civis.py`

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host` | `str` | `0.0.0.0` | HTTP Server bind address |
| `--port` | `int` | `8000` | HTTP Server port |
| `--camera` | `int/str` | `0` | Camera device index (`0`), video file (`video.mp4`), or RTSP URL |
| `--camera-id` | `str` | `CAM_01` | Unique camera ID identifier |
| `--width` | `int` | `1280` | Target frame capture width |
| `--height` | `int` | `720` | Target frame capture height |
| `--fps` | `float` | `30.0` | Ingestion FPS limit |
| `--sahi` | `str` | `auto` | SAHI mode: `full_frame`, `sliced_only`, `hybrid`, `auto`, `adaptive` |
| `--face-detector` | `str` | `yunet` | Face detector backend: `yunet`, `scrfd`, `heuristic`, `mock` |
| `--use-mock` | `flag` | `False` | Run with deterministic synthetic test pipeline |
| `--open-browser` | `flag` | `False` | Automatically open default web browser to console |

---

## 6. Privacy & Safety Guarantees

1. **Local-Only Execution**: Raw video frames and neural embeddings remain strictly on the host machine.
2. **Zero Cloud Upload**: No telemetry, images, or metadata are transmitted to external services.
3. **No Automatic Video Recording**: Video frames are processed in-memory and discarded frame-by-frame.
4. **Explicit Forensic Retention**: Cryptographic hash chains and evidence packages are only generated when explicitly requested via the Evidence Subsystem or `--save-evidence`.

---

## 7. Troubleshooting Camera Access

1. **Camera cannot be opened (`[!] Hardware webcam could not be opened`)**:
   - Verify that other applications (Zoom, Teams, Camera app) are closed.
   - On Windows, ensure camera permissions are granted under *Settings > Privacy & Security > Camera*.
   - If using an external USB camera, test with index 1: `python run_civis.py --camera 1`.
   - When running in headless environments or VMs without webcam hardware, CIVIS automatically switches to an animated synthetic test stream.
2. **High Latency or Low FPS**:
   - Reduce capture resolution: `python run_civis.py --width 640 --height 480 --fps 15`.
   - Use default `auto` SAHI mode to avoid heavy tiling on high resolutions.
