"""
CIVIS-CORE: Unified Live Surveillance Operator Console & API Launcher

Starts the CIVIS-CORE high-performance backend, connects the real webcam / video source,
and serves the operator monitoring console with live MJPEG streaming and WebSocket telemetry.
"""

import argparse
import logging
import os
import sys
import webbrowser
from fastapi.staticfiles import StaticFiles
import uvicorn

from civis.api.dependencies import APIDependencies
from civis.api.engine import APIEngine
from civis.api.models import APIConfig
from civis.config.engine import ConfigEngine
from civis.config.models import CIVISConfig
from civis.evidence.engine import EvidenceEngine
from civis.evidence.models import EvidenceEngineConfig
from civis.observability.engine import ObservabilityEngine
from civis.observability.models import ObservabilityConfig
from civis.detection.models import DetectionMode
from civis.risk.engine import RiskEngine
from civis.risk.models import RiskEngineConfig
from civis.runtime.engine import RuntimeEngine
from civis.runtime.models import (
    CameraRuntimeConfig,
    PipelineRuntimeConfig,
    SourceType,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("civis.launcher")


def create_civis_app(
    camera_source: str = "0",
    camera_id: str = "CAM_01",
    target_width: int = 1280,
    target_height: int = 720,
    fps: float = 30.0,
    use_mock: bool = False,
    sahi_mode: str = "auto",
    face_backend: str = "yunet",
    auth_enabled: bool = False,
    api_key: str = "civis-secret-key-123",
):
    """Initializes and connects all CIVIS-CORE subsystems into a unified FastAPI application."""
    print("=" * 80)
    print(" CIVIS-CORE: LIVE SURVEILLANCE & OPERATOR CONSOLE LAUNCHER")
    print("=" * 80)
    print(f"[*] Camera Device / Source : {camera_source}")
    print(f"[*] Target Stream Format   : {target_width}x{target_height} @ {fps} FPS")
    print(f"[*] AI Pipeline Mode       : {'MOCK (Synthetic)' if use_mock else 'NEURAL (Live AI)'}")
    print(f"[*] SAHI Object Detection  : {sahi_mode.upper()}")
    print(f"[*] Face Detector Backend  : {face_backend.upper()}")
    print(f"[*] API Key Authentication : {'ENABLED' if auth_enabled else 'DISABLED (Local Dev)'}")
    print("=" * 80)

    # 1. Initialize Subsystem Engines
    cfg_engine = ConfigEngine(CivisConfig(environment="development" if not auth_enabled else "production"))
    obs_engine = ObservabilityEngine(ObservabilityConfig(use_mock=use_mock))
    evd_engine = EvidenceEngine(EvidenceEngineConfig(use_mock=use_mock))
    rsk_engine = RiskEngine(RiskEngineConfig(use_mock=use_mock))

    is_num = camera_source.isdigit() if isinstance(camera_source, str) else isinstance(camera_source, int)
    source_type = SourceType.WEBCAM if is_num else SourceType.FILE

    cam_runtime_cfg = CameraRuntimeConfig(
        camera_id=camera_id,
        source=int(camera_source) if is_num else camera_source,
        source_type=source_type,
        width=target_width,
        height=target_height,
        fps_limit=fps,
        use_mock=use_mock,
    )

    rt_engine = RuntimeEngine(
        PipelineRuntimeConfig(
            use_mock=use_mock,
            cameras=[cam_runtime_cfg],
        ),
        observability=obs_engine,
    )

    # 2. Inject Subsystems into API Gateway
    api_deps = APIDependencies(
        runtime_engine=rt_engine,
        observability_engine=obs_engine,
        config_engine=cfg_engine,
        evidence_engine=evd_engine,
        risk_engine=rsk_engine,
    )

    api_config = APIConfig(
        use_mock=use_mock,
        authentication_enabled=auth_enabled,
        api_key=api_key if auth_enabled else None,
        websocket_enabled=True,
    )

    api_engine = APIEngine(config=api_config, dependencies=api_deps)
    api_engine.attach_runtime_events(rt_engine)
    app = api_engine.get_app()

    # 3. Mount Frontend Static Assets if Built
    dist_dir = os.path.join(os.path.dirname(__file__), "frontend", "civis-dashboard", "dist")
    if os.path.exists(dist_dir) and os.path.isdir(dist_dir):
        logger.info("[+] Mounting production dashboard UI from: %s", dist_dir)
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")
    else:
        logger.info("[*] Dashboard build not found at %s. API and stream endpoints active.", dist_dir)

    # Start runtime engine cameras automatically
    rt_engine.start()

    return app, rt_engine


def parse_args():
    parser = argparse.ArgumentParser(description="CIVIS-CORE Unified Live Surveillance & Operator Console")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP Server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP Server port (default: 8000)")
    parser.add_argument("--camera", default="0", help="Webcam device index (0) or video file path (default: 0)")
    parser.add_argument("--camera-id", default="CAM_01", help="Camera identifier string (default: CAM_01)")
    parser.add_argument("--width", type=int, default=1280, help="Target capture width (default: 1280)")
    parser.add_argument("--height", type=int, default=720, help="Target capture height (default: 720)")
    parser.add_argument("--fps", type=float, default=30.0, help="Target ingestion FPS limit (default: 30.0)")
    parser.add_argument("--use-mock", action="store_true", help="Run with deterministic synthetic mock pipeline")
    parser.add_argument("--sahi", default="auto", choices=["full_frame", "sliced_only", "hybrid", "auto", "adaptive"], help="SAHI small-object detection mode")
    parser.add_argument("--face-detector", default="yunet", choices=["yunet", "scrfd", "heuristic", "mock"], help="Face detector backend")
    parser.add_argument("--open-browser", action="store_true", help="Automatically open operator console in default browser")
    return parser.parse_args()


def main():
    args = parse_args()
    app, rt_engine = create_civis_app(
        camera_source=args.camera,
        camera_id=args.camera_id,
        target_width=args.width,
        target_height=args.height,
        fps=args.fps,
        use_mock=args.use_mock,
        sahi_mode=args.sahi,
        face_backend=args.face_detector,
    )

    url = f"http://localhost:{args.port}"
    print("\n" + "=" * 80)
    print(f" [★] CIVIS-CORE OPERATOR CONSOLE READY: {url}")
    print(f" [★] Live Webcam MJPEG Stream       : {url}/cameras/{args.camera_id}/stream")
    print(f" [★] Real-Time Telemetry WebSocket : ws://localhost:{args.port}/ws/events")
    print(f" [★] Interactive API Documentation  : {url}/docs")
    print("=" * 80 + "\n")

    if args.open_browser:
        webbrowser.open(url)

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        logger.info("Stopping CIVIS-CORE runtime engine...")
        rt_engine.stop()


if __name__ == "__main__":
    main()
