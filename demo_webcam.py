"""
CIVIS-CORE: Real Laptop Webcam Integration & Live Operator Visualization Demo

Connects a live webcam/video source to the complete CIVIS-CORE pipeline:
Webcam -> Ingestion -> Detection (+ SAHI) -> Tracking -> Face Detection ->
Identity -> Re-ID -> Behavior -> Event Intelligence -> Risk -> Evidence -> Observability.
"""

import argparse
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from civis.behavior.models import BehaviorConfig
from civis.behavior.factory import create_behavior_engine
from civis.detection.models import (
    BoundingBox,
    DetectionMode,
    DetectorConfig,
    SAHIConfig,
)
from civis.detection.factory import create_detector
from civis.event_intelligence.factory import create_event_intelligence_engine
from civis.event_intelligence.models import EventIntelligenceConfig
from civis.evidence.factory import create_evidence_engine
from civis.evidence.models import EvidenceEngineConfig
from civis.identity.factory import create_identity_engine
from civis.identity.models import FaceDetectorConfig, IdentityConfig
from civis.ingestion.factory import create_video_source
from civis.ingestion.models import CameraConfig, CameraStatus, FramePacket, SourceType
from civis.observability.engine import ObservabilityEngine
from civis.observability.models import ObservabilityConfig
from civis.reid.factory import create_cross_camera_reid_engine
from civis.reid.models import ReIDEngineConfig
from civis.risk.factory import create_risk_engine
from civis.risk.models import RiskEngineConfig
from civis.runtime.models import StageConfig
from civis.runtime.pipeline import (
    BehaviorStage,
    DetectionStage,
    EventIntelligenceStage,
    EvidenceStage,
    IdentityStage,
    PipelineContext,
    ReIDStage,
    RiskAssessmentStage,
    SequentialPipeline,
    TrackingStage,
)
from civis.tracking.factory import create_tracker
from civis.tracking.models import TrackerConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("civis.demo_webcam")


# Palette for track IDs (distinct high-contrast colors)
TRACK_COLORS = [
    (50, 205, 50),   # Lime Green
    (255, 140, 0),   # Dark Orange
    (30, 144, 255),  # Dodger Blue
    (238, 130, 238), # Violet
    (255, 215, 0),   # Gold
    (0, 255, 255),   # Yellow
    (255, 105, 180), # Hot Pink
    (138, 43, 226),  # Blue Violet
]


def get_color_for_id(track_id: int) -> Tuple[int, int, int]:
    return TRACK_COLORS[abs(track_id) % len(TRACK_COLORS)]


def draw_pipeline_overlays(
    frame: np.ndarray,
    context: PipelineContext,
    fps_capture: float,
    fps_processed: float,
    latency_ms: float,
    camera_id: str,
    privacy_mode: bool = True,
) -> np.ndarray:
    """Renders comprehensive real-time overlays for all pipeline subsystems."""
    vis = frame.copy()
    h, w = vis.shape[:2]

    # --- 1. Top Privacy & System Status Banner ---
    overlay_header = vis.copy()
    cv2.rectangle(overlay_header, (0, 0), (w, 42), (20, 24, 28), -1)
    cv2.addWeighted(overlay_header, 0.85, vis, 0.15, 0, vis)

    # Status LED
    cv2.circle(vis, (18, 21), 6, (0, 230, 120), -1)
    header_text = f"CIVIS-CORE | {camera_id} | LOCAL STREAM"
    if privacy_mode:
        header_text += " [PRIVACY-SAFE: LOCAL ONLY - NO CLOUD]"
    cv2.putText(vis, header_text, (32, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)

    time_str = time.strftime("%H:%M:%S")
    cv2.putText(vis, time_str, (w - 95, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 230, 120), 1, cv2.LINE_AA)

    # --- 2. Object Detections & Tracking Overlays ---
    track_boxes = {}
    if context.track_result and context.track_result.tracks:
        for trk in context.track_result.tracks:
            color = get_color_for_id(trk.track_id)
            bx1, by1 = max(0, int(trk.bbox.x1)), max(0, int(trk.bbox.y1))
            bx2, by2 = min(w - 1, int(trk.bbox.x2)), min(h - 1, int(trk.bbox.y2))
            track_boxes[trk.track_id] = (bx1, by1, bx2, by2)

            # Main bounding box
            cv2.rectangle(vis, (bx1, by1), (bx2, by2), color, 2)

            # Label badge
            label = f"#{trk.track_id} {trk.class_name} {trk.confidence:.0%}"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(vis, (bx1, max(0, by1 - 20)), (bx1 + lw + 8, by1), color, -1)
            cv2.putText(vis, label, (bx1 + 4, max(12, by1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

    # --- 3. Face Detection & Identity Badges ---
    if context.identity_result and context.identity_result.identities:
        for ident in context.identity_result.identities:
            tid = ident.track_id
            name = ident.name if ident.state.value == "known" else "UNKNOWN"
            badge = f"Face: {name}"

            if tid in track_boxes:
                bx1, by1, bx2, by2 = track_boxes[tid]
                # Face upper sub-box
                face_h = int((by2 - by1) * 0.35)
                cv2.rectangle(vis, (bx1 + 4, by1 + 4), (bx2 - 4, by1 + face_h), (255, 255, 0), 1)

                # Identity badge below person box
                (iw, ih), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(vis, (bx1, by2), (bx1 + iw + 8, by2 + 18), (40, 40, 40), -1)
                cv2.rectangle(vis, (bx1, by2), (bx1 + iw + 8, by2 + 18), (255, 255, 0), 1)
                cv2.putText(vis, badge, (bx1 + 4, by2 + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1, cv2.LINE_AA)

    # --- 4. Cross-Camera Re-ID Global Entity ---
    if context.reid_result and context.reid_result.global_entities:
        for entity in context.reid_result.global_entities:
            for b in entity.associated_tracks:
                if b.camera_id == camera_id and b.track_id in track_boxes:
                    bx1, by1, bx2, by2 = track_boxes[b.track_id]
                    reid_tag = f"Global: {entity.global_entity_id[-6:]}"
                    cv2.putText(vis, reid_tag, (bx1 + 4, by1 + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (200, 200, 255), 1, cv2.LINE_AA)

    # --- 5. Behavior & Loitering Indicators ---
    if context.behavior_result and context.behavior_result.observations:
        for obs in context.behavior_result.observations:
            if obs.track_id in track_boxes:
                bx1, by1, _, _ = track_boxes[obs.track_id]
                if obs.state.value == "loitering":
                    cv2.putText(vis, "! LOITERING !", (bx1 + 4, by1 + 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2, cv2.LINE_AA)
                elif obs.state.value == "dwelling":
                    cv2.putText(vis, "Dwelling", (bx1 + 4, by1 + 48), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 165, 255), 1, cv2.LINE_AA)

    # --- 6. Risk Alerts Header Badge (Top-Right) ---
    if context.risk_result and context.risk_result.assessments:
        max_assessment = max(context.risk_result.assessments, key=lambda a: a.severity_score, default=None)
        if max_assessment and max_assessment.severity_score >= 40.0:
            score = max_assessment.severity_score
            sev = max_assessment.severity.value.upper()
            risk_color = (0, 0, 255) if score >= 70.0 else (0, 165, 255)
            badge_text = f"RISK: {sev} ({score:.0f})"
            cv2.rectangle(vis, (w - 260, 50), (w - 20, 80), risk_color, -1)
            cv2.putText(vis, badge_text, (w - 245, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

    # --- 7. Bottom Diagnostic HUD ---
    hud_h = 58
    overlay_hud = vis.copy()
    cv2.rectangle(overlay_hud, (0, h - hud_h), (w, h), (15, 18, 22), -1)
    cv2.addWeighted(overlay_hud, 0.88, vis, 0.12, 0, vis)

    # Row 1: Throughput and Latency
    hud_line1 = (
        f"CAP FPS: {fps_capture:>4.1f} | "
        f"PROC FPS: {fps_processed:>4.1f} | "
        f"LATENCY: {latency_ms:>5.1f} ms | "
        f"DIM: {w}x{h}"
    )
    cv2.putText(vis, hud_line1, (16, h - 34), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (220, 220, 220), 1, cv2.LINE_AA)

    # Row 2: Per-Stage Timings Breakdown
    st = context.stage_timings_ms
    hud_line2 = (
        f"Det: {st.get('detection', 0):.1f}ms | "
        f"Trk: {st.get('tracking', 0):.1f}ms | "
        f"Id: {st.get('identity', 0):.1f}ms | "
        f"ReID: {st.get('reid', 0):.1f}ms | "
        f"Beh: {st.get('behavior', 0):.1f}ms | "
        f"Risk: {st.get('risk', 0):.1f}ms | "
        f"[q: Quit  p: Pause  s: Snapshot]"
    )
    cv2.putText(vis, hud_line2, (16, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 210, 150), 1, cv2.LINE_AA)

    return vis


def build_live_pipeline(
    camera_id: str,
    sahi_mode: DetectionMode,
    confidence_threshold: float,
    face_backend: str,
    use_mock: bool,
    save_evidence: bool,
) -> Tuple[SequentialPipeline, Optional[ObservabilityEngine], Optional[Any]]:
    """Constructs the complete CIVIS sequential pipeline for webcam execution."""
    # Detection stage
    sahi_cfg = SAHIConfig(
        mode=sahi_mode,
        slice_height=320,
        slice_width=320,
        auto_min_dimension=720,
        slice_conf_threshold=confidence_threshold,
    )
    det_cfg = DetectorConfig(
        use_mock=use_mock,
        conf_threshold=confidence_threshold,
        sahi_config=sahi_cfg,
    )
    detector = create_detector(det_cfg)

    # Tracking stage
    tracker = create_tracker(TrackerConfig(use_mock=use_mock))

    # Face & Identity stage
    face_cfg = FaceDetectorConfig(backend=face_backend if not use_mock else "mock")
    ident_cfg = IdentityConfig(use_mock=use_mock, detector=face_cfg, store_face_crops=False)
    identity_engine = create_identity_engine(ident_cfg)

    # Re-ID, Behavior, Event, Risk stages
    reid_engine = create_cross_camera_reid_engine(ReIDEngineConfig(use_mock=use_mock))
    behavior_engine = create_behavior_engine(BehaviorConfig(use_mock=use_mock))
    event_engine = create_event_intelligence_engine(EventIntelligenceConfig(use_mock=use_mock))
    risk_engine = create_risk_engine(RiskEngineConfig(use_mock=use_mock))

    # Evidence engine (only if explicitly enabled)
    evidence_engine = None
    if save_evidence:
        evidence_engine = create_evidence_engine(EvidenceEngineConfig(use_mock=use_mock))

    # Observability
    obs_engine = ObservabilityEngine(ObservabilityConfig(use_mock=use_mock))

    stages = [
        DetectionStage(detector, enabled=True),
        TrackingStage(tracker, enabled=True),
        IdentityStage(identity_engine, enabled=True),
        ReIDStage(reid_engine, enabled=True),
        BehaviorStage(behavior_engine, enabled=True),
        EventIntelligenceStage(event_engine, enabled=True),
        RiskAssessmentStage(risk_engine, enabled=True),
    ]

    if evidence_engine is not None:
        stages.append(EvidenceStage(evidence_engine, enabled=True))

    pipeline = SequentialPipeline(stages=stages)
    return pipeline, obs_engine, evidence_engine


def make_mock_webcam_packet(camera_id: str, frame_num: int, width: int, height: int) -> FramePacket:
    """Generates synthetic camera frames when hardware camera is not accessible."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (30, 32, 36)

    # Grid background pattern
    for y in range(0, height, 40):
        cv2.line(frame, (0, y), (width, y), (40, 44, 50), 1)
    for x in range(0, width, 40):
        cv2.line(frame, (x, 0), (x, height), (40, 44, 50), 1)

    # Animated person target
    x_offset = int((frame_num * 6) % (width - 150))
    y_offset = int(height * 0.25)
    pw, ph = 100, 220

    # Person body
    cv2.rectangle(frame, (x_offset, y_offset), (x_offset + pw, y_offset + ph), (60, 140, 220), -1)
    # Person face
    fx, fy = x_offset + 25, y_offset + 15
    cv2.rectangle(frame, (fx, fy), (fx + 50, fy + 55), (220, 200, 180), -1)

    cv2.putText(
        frame,
        "SYNTHETIC TEST CAMERA [MOCK INGESTION]",
        (width // 2 - 200, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 200, 255),
        2,
    )

    return FramePacket.create(
        camera_id=camera_id,
        frame_number=frame_num,
        frame=frame,
        timestamp=time.time(),
    )


def run_webcam_demo(
    camera_source: Any = 0,
    camera_id: str = "WEBCAM_01",
    target_width: int = 1280,
    target_height: int = 720,
    target_fps: float = 30.0,
    frame_interval: int = 1,
    sahi_mode: str = "auto",
    conf_threshold: float = 0.35,
    face_detector_backend: str = "yunet",
    use_mock: bool = False,
    save_evidence: bool = False,
    export_dir: str = "./evidence_store",
    no_display: bool = False,
    max_frames: Optional[int] = None,
) -> int:
    """Main execution loop for real laptop webcam integration test."""
    print("=" * 80)
    print(" CIVIS-CORE: REAL WEBCAM INTEGRATION & DEMO PIPELINE")
    print("=" * 80)
    print(f"[*] Camera Source     : {camera_source}")
    print(f"[*] Target Resolution : {target_width}x{target_height} @ {target_fps} FPS")
    print(f"[*] SAHI Mode         : {sahi_mode.upper()} (conf={conf_threshold})")
    print(f"[*] Face Detector     : {face_detector_backend.upper()}")
    print(f"[*] AI Backend Mode   : {'MOCK' if use_mock else 'NEURAL / LIVE'}")
    print(f"[*] Evidence Saving   : {'ENABLED' if save_evidence else 'DISABLED (Privacy Default)'}")
    print(f"[*] Display GUI       : {'DISABLED (Headless)' if no_display else 'ENABLED'}")
    print("=" * 80)

    # Resolve SAHI Mode
    try:
        resolved_sahi_mode = DetectionMode(sahi_mode.lower())
    except ValueError:
        logger.warning("Unknown SAHI mode '%s'. Defaulting to AUTO.", sahi_mode)
        resolved_sahi_mode = DetectionMode.AUTO

    # 1. Initialize Video Source
    is_numeric = isinstance(camera_source, int) or (isinstance(camera_source, str) and camera_source.isdigit())
    source_type = SourceType.WEBCAM if is_numeric else SourceType.FILE

    cam_config = CameraConfig(
        camera_id=camera_id,
        name="Laptop Webcam",
        source_type=source_type,
        source=int(camera_source) if is_numeric else camera_source,
        fps_limit=target_fps,
        width=target_width,
        height=target_height,
        drop_outdated_frames=True,
    )

    video_source = None
    use_fallback_mock = use_mock

    if not use_mock:
        logger.info("Initializing camera capture on source: %s ...", camera_source)
        try:
            video_source = create_video_source(cam_config)
            video_source.start()
            # Give device up to 2 seconds to initialize
            t_wait = time.time()
            first_packet = None
            while time.time() - t_wait < 2.0:
                first_packet = video_source.read(timeout=0.3)
                if first_packet is not None:
                    break
                time.sleep(0.1)

            if first_packet is None or video_source.get_status() in (CameraStatus.ERROR, CameraStatus.STOPPED):
                logger.warning(
                    "[!] Hardware webcam (index %s) could not be opened. "
                    "Falling back to synthetic mock stream for pipeline validation.",
                    camera_source,
                )
                use_fallback_mock = True
                if video_source:
                    video_source.stop()
                    video_source = None
            else:
                logger.info("[+] Hardware webcam successfully opened: %s", first_packet.dimensions)
        except Exception as e:
            logger.warning("[!] Failed to open camera hardware: %s. Using synthetic stream.", e)
            use_fallback_mock = True

    # 2. Build Pipeline
    pipeline, obs_engine, evidence_engine = build_live_pipeline(
        camera_id=camera_id,
        sahi_mode=resolved_sahi_mode,
        confidence_threshold=conf_threshold,
        face_backend=face_detector_backend,
        use_mock=use_fallback_mock,
        save_evidence=save_evidence,
    )

    window_name = "CIVIS-CORE Live Operator Console [Webcam]"
    if not no_display:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, min(1280, target_width), min(720, target_height))

    frame_counter = 0
    processed_counter = 0
    t_start = time.time()
    last_fps_calc_time = t_start
    frames_in_second = 0
    current_fps = 0.0

    latencies: List[float] = []
    is_paused = False

    logger.info("[+] Pipeline loop running. Press 'q' to quit.")

    try:
        while True:
            if max_frames is not None and frame_counter >= max_frames:
                logger.info("Reached max_frames limit (%d). Exiting loop cleanly.", max_frames)
                break

            loop_start = time.perf_counter()

            # Read frame
            if video_source is not None:
                packet = video_source.read(timeout=0.2)
            else:
                packet = make_mock_webcam_packet(camera_id, frame_counter + 1, target_width, target_height)

            if packet is None:
                time.sleep(0.01)
                continue

            frame_counter += 1
            frames_in_second += 1

            # Update FPS calculation every second
            now = time.time()
            if now - last_fps_calc_time >= 1.0:
                current_fps = frames_in_second / (now - last_fps_calc_time)
                frames_in_second = 0
                last_fps_calc_time = now

            if is_paused:
                time.sleep(0.05)
                continue

            # Frame skip / interval
            if frame_interval > 1 and (frame_counter % frame_interval != 0):
                continue

            # Process through CIVIS sequential pipeline
            context = PipelineContext(packet=packet, camera_id=camera_id)
            context = pipeline.execute(context)
            processed_counter += 1

            proc_latency_ms = (time.perf_counter() - loop_start) * 1000.0
            latencies.append(proc_latency_ms)
            if len(latencies) > 60:
                latencies.pop(0)
            avg_lat = sum(latencies) / len(latencies)

            # Record in Observability
            if obs_engine:
                for sname, stiming in context.stage_timings_ms.items():
                    obs_engine.record_stage_latency(sname, stiming, camera_id)

            # Render Overlays
            annotated_frame = draw_pipeline_overlays(
                frame=packet.frame,
                context=context,
                fps_capture=current_fps,
                fps_processed=round(1000.0 / avg_lat, 1) if avg_lat > 0 else current_fps,
                latency_ms=avg_lat,
                camera_id=camera_id,
                privacy_mode=not save_evidence,
            )

            # Display
            if not no_display:
                cv2.imshow(window_name, annotated_frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):  # 'q' or ESC
                    logger.info("Exit signal received from user.")
                    break
                elif key == ord("p"):
                    is_paused = not is_paused
                    logger.info("Pipeline %s.", "PAUSED" if is_paused else "RESUMED")
                elif key == ord("s") and evidence_engine:
                    timeline = evidence_engine.build_timeline()
                    logger.info("[Snapshot] Total evidence records captured: %d", timeline.total_records)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received.")

    finally:
        total_time = time.time() - t_start
        if video_source is not None:
            video_source.stop()
        if not no_display:
            cv2.destroyAllWindows()

        print("\n" + "=" * 80)
        print(" CIVIS-CORE WEBCAM RUN SUMMARY")
        print("=" * 80)
        print(f"Total Capture Frames   : {frame_counter}")
        print(f"Total Processed Frames : {processed_counter}")
        print(f"Total Execution Time   : {total_time:.2f} s")
        if total_time > 0:
            print(f"Average Throughput     : {processed_counter / total_time:.1f} FPS")
        if latencies:
            print(f"Average Frame Latency  : {sum(latencies) / len(latencies):.2f} ms")

        # Export evidence package if enabled
        if save_evidence and evidence_engine:
            timeline = evidence_engine.build_timeline(camera_id=camera_id)
            pkg_path = os.path.join(export_dir, f"incident_{camera_id}_{int(time.time())}")
            manifest = evidence_engine.export_forensic_package(timeline, pkg_path)
            print(f"\n[+] Forensic Package Exported to: {pkg_path}")
            print(f"    - Total Evidence Records : {manifest.total_evidence_records}")
            print(f"    - Root Ledger Hash       : {manifest.root_ledger_hash[:20]}...")
            print(f"    - Package Integrity      : {'VALID' if manifest.is_valid else 'INVALID'}")

        print("=" * 80)

    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="CIVIS-CORE Real Laptop Webcam Integration & Live Demo")
    parser.add_argument("--camera", default=0, help="Webcam device index (e.g. 0) or video file path (default: 0)")
    parser.add_argument("--camera-id", default="WEBCAM_01", help="Camera identifier string (default: WEBCAM_01)")
    parser.add_argument("--width", type=int, default=1280, help="Target frame capture width (default: 1280)")
    parser.add_argument("--height", type=int, default=720, help="Target frame capture height (default: 720)")
    parser.add_argument("--fps", type=float, default=30.0, help="Target ingestion FPS cap (default: 30.0)")
    parser.add_argument("--frame-interval", type=int, default=1, help="Process every N-th frame (default: 1)")
    parser.add_argument("--sahi", default="auto", choices=["full_frame", "sliced_only", "hybrid", "auto", "adaptive"], help="SAHI small object detection mode (default: auto)")
    parser.add_argument("--conf", type=float, default=0.35, help="Detection confidence threshold (default: 0.35)")
    parser.add_argument("--face-detector", default="yunet", choices=["yunet", "scrfd", "heuristic", "mock"], help="Face detector backend (default: yunet)")
    parser.add_argument("--use-mock", action="store_true", help="Run with mock AI models (deterministic/offline)")
    parser.add_argument("--save-evidence", action="store_true", help="Explicitly enable evidence ledger recording and forensic export")
    parser.add_argument("--export-dir", default="./evidence_store", help="Target directory for forensic evidence packages")
    parser.add_argument("--no-display", action="store_true", help="Run in headless mode without opening GUI window")
    parser.add_argument("--max-frames", type=int, default=None, help="Stop after processing N frames")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cam_val = args.camera
    if isinstance(cam_val, str) and cam_val.isdigit():
        cam_val = int(cam_val)

    sys.exit(
        run_webcam_demo(
            camera_source=cam_val,
            camera_id=args.camera_id,
            target_width=args.width,
            target_height=args.height,
            target_fps=args.fps,
            frame_interval=args.frame_interval,
            sahi_mode=args.sahi,
            conf_threshold=args.conf,
            face_detector_backend=args.face_detector,
            use_mock=args.use_mock,
            save_evidence=args.save_evidence,
            export_dir=args.export_dir,
            no_display=args.no_display,
            max_frames=args.max_frames,
        )
    )
