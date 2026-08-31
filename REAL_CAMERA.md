# CIVIS-CORE: Real Laptop Webcam Integration & Live Demo

This guide explains how to run the CIVIS-CORE computer vision and surveillance analytics pipeline against a live local webcam, video file, or RTSP stream.

---

## 1. Prerequisites & Dependencies

The webcam demo relies on the existing CIVIS-CORE stack:

```bash
# Core dependencies
pip install opencv-python numpy pydantic

# Optional neural model backends (YOLO, SAHI, PyTorch)
pip install torch ultralytics sahi
```

> **Note**: If neural weights or GPU libraries are not installed, pass `--use-mock` or rely on the automatic heuristic fallback mode.

---

## 2. Quick Start

### Basic Webcam Execution (Live Display)

```bash
# Start with default webcam (Device Index 0 at 1280x720)
python demo_webcam.py
```

### High-Performance Lightweight Stream (640x480, 15 FPS)

```bash
python demo_webcam.py --camera 0 --width 640 --height 480 --fps 15
```

### Adaptive SAHI Small-Object Mode with Real Face Detection

```bash
python demo_webcam.py --sahi adaptive --face-detector yunet --conf 0.30
```

### Deterministic Offline / Testing Mode (Headless)

```bash
python demo_webcam.py --use-mock --no-display --max-frames 50
```

---

## 3. Command-Line Options Reference

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--camera` | `int/str` | `0` | Camera device index (e.g. `0`, `1`), video file path (`test.mp4`), or RTSP URL |
| `--camera-id` | `str` | `WEBCAM_01` | Unique camera ID identifier used in logs, traces, and evidence |
| `--width` | `int` | `1280` | Target capture width in pixels |
| `--height` | `int` | `720` | Target capture height in pixels |
| `--fps` | `float` | `30.0` | Target ingestion FPS cap |
| `--frame-interval` | `int` | `1` | Frame skip interval (e.g., `2` to process every 2nd frame) |
| `--sahi` | `str` | `auto` | SAHI mode: `full_frame`, `sliced_only`, `hybrid`, `auto`, `adaptive` |
| `--conf` | `float` | `0.35` | Object detection confidence threshold |
| `--face-detector` | `str` | `yunet` | Face detector backend: `yunet`, `scrfd`, `heuristic`, `mock` |
| `--use-mock` | `flag` | `False` | Run with deterministic synthetic test models without neural weight files |
| `--save-evidence` | `flag` | `False` | Explicitly enable cryptographic evidence logging and package export |
| `--export-dir` | `str` | `./evidence_store` | Target root directory for forensic export packages |
| `--no-display` | `flag` | `False` | Headless mode (no OpenCV GUI window, for CI/remote servers) |
| `--max-frames` | `int` | `None` | Automatically stop after processing $N$ frames |

---

## 4. Live Visualizer Overlays

When running with GUI display enabled (`demo_webcam.py`), the following overlays are rendered in real-time:

1. **Privacy Header Banner (Top)**:
   - Green indicator confirming local-only stream execution.
   - Timestamp, Camera ID, and Privacy assurance badge.
2. **Track Bounding Boxes**:
   - Distinct color-coded bounding boxes per Track ID.
   - Class label (e.g., `#1 person 92%`).
3. **Face Detection & Identity**:
   - Cyan sub-box around detected faces with facial landmarks.
   - Identity badge: `Face: UNKNOWN` or enrolled person name.
4. **Cross-Camera Re-ID Tag**:
   - Global Entity ID assigned to tracked person (`Global: XXXXXX`).
5. **Behavior Indicators**:
   - Dynamic movement warnings (e.g., `! LOITERING !`, `Dwelling`).
6. **Risk Assessment Banner (Top-Right)**:
   - Colored badge when risk score $\ge 40$ (Amber for Moderate, Red for High/Critical).
7. **Performance & Diagnostic HUD (Bottom)**:
   - Real-time Capture FPS & Processed FPS.
   - End-to-end latency and per-stage latency breakdown (`Det`, `Trk`, `Id`, `ReID`, `Beh`, `Risk`).

---

## 5. Interactive Keyboard Controls

While the OpenCV display window is focused:

- **`q`** or **`ESC`**: Gracefully stop the stream and exit.
- **`p`**: Pause / Resume pipeline processing.
- **`s`**: Take an immediate evidence ledger snapshot / audit check.

---

## 6. Privacy & Safety Controls

By default:
- **No Cloud Upload**: All inference and processing remain strictly on the local machine.
- **No Permanent Video Storage**: Raw webcam video is discarded frame-by-frame; only in-memory tensors are used during active analysis.
- **Evidence Opt-In**: Evidence logging and forensic packages are **only** generated if the `--save-evidence` flag is explicitly provided.

---

## 7. Troubleshooting Camera Access

1. **Camera cannot be opened (`[!] Hardware webcam could not be opened`)**:
   - Verify that another application (Zoom, Teams, Camera app) is not holding an exclusive lock on the camera device.
   - Try specifying an alternate camera index: `python demo_webcam.py --camera 1`
   - On Windows, verify camera privacy permissions under *Settings > Privacy & Security > Camera*.
   - If no hardware camera is present (e.g. headless VM or Docker container), `demo_webcam.py` automatically falls back to an animated synthetic test stream.
2. **High Latency or Low FPS**:
   - Reduce capture resolution: `--width 640 --height 480`
   - Enable frame skipping: `--frame-interval 2`
   - Use `full_frame` or `auto` SAHI mode instead of forced slicing: `--sahi auto`
