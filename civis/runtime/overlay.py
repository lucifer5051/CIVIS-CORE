"""
CIVIS-CORE Pipeline Visualizer & Overlay Renderer
Renders high-contrast bounding boxes, track labels, face badges, Re-ID tags, behavior indicators,
risk alerts, and diagnostic HUD onto video frames.
"""

import time
from typing import Optional, Tuple
import cv2
import numpy as np

from civis.runtime.pipeline import PipelineContext

# High-contrast color palette for track visualization
TRACK_PALETTE = [
    (50, 205, 50),   # Lime Green
    (255, 140, 0),   # Dark Orange
    (30, 144, 255),  # Dodger Blue
    (238, 130, 238), # Violet
    (255, 215, 0),   # Gold
    (0, 255, 255),   # Yellow
    (255, 105, 180), # Hot Pink
    (138, 43, 226),  # Blue Violet
]


def get_track_color(track_id: int) -> Tuple[int, int, int]:
    return TRACK_PALETTE[abs(track_id) % len(TRACK_PALETTE)]


def render_pipeline_overlay(
    frame: np.ndarray,
    context: Optional[PipelineContext] = None,
    camera_id: str = "CAM_01",
    fps: float = 0.0,
    latency_ms: float = 0.0,
    privacy_mode: bool = True,
) -> np.ndarray:
    """Renders comprehensive real-time overlays for all pipeline subsystems."""
    vis = frame.copy()
    h, w = vis.shape[:2]

    # 1. Header Banner
    overlay_header = vis.copy()
    cv2.rectangle(overlay_header, (0, 0), (w, 38), (18, 22, 26), -1)
    cv2.addWeighted(overlay_header, 0.85, vis, 0.15, 0, vis)

    # Status LED
    cv2.circle(vis, (16, 19), 5, (0, 230, 120), -1)
    header_text = f"CIVIS-CORE | {camera_id}"
    if privacy_mode:
        header_text += " [LOCAL STREAM - PRIVACY SAFE]"
    cv2.putText(vis, header_text, (28, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (240, 240, 240), 1, cv2.LINE_AA)

    time_str = time.strftime("%H:%M:%S")
    cv2.putText(vis, time_str, (w - 85, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 230, 120), 1, cv2.LINE_AA)

    if context is None:
        return vis

    # 2. Object Detections & Tracking Overlays
    track_boxes = {}
    if context.track_result and context.track_result.tracks:
        for trk in context.track_result.tracks:
            color = get_track_color(trk.track_id)
            bx1, by1 = max(0, int(trk.bbox.x1)), max(0, int(trk.bbox.y1))
            bx2, by2 = min(w - 1, int(trk.bbox.x2)), min(h - 1, int(trk.bbox.y2))
            track_boxes[trk.track_id] = (bx1, by1, bx2, by2)

            cv2.rectangle(vis, (bx1, by1), (bx2, by2), color, 2)

            label = f"#{trk.track_id} {trk.class_name} {trk.confidence:.0%}"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
            cv2.rectangle(vis, (bx1, max(0, by1 - 18)), (bx1 + lw + 6, by1), color, -1)
            cv2.putText(vis, label, (bx1 + 3, max(10, by1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)

    # 3. Face Detections & Identity
    if context.identity_result and context.identity_result.identities:
        for ident in context.identity_result.identities:
            tid = ident.track_id
            name = ident.name if ident.state.value == "known" else "UNKNOWN"
            badge = f"Face: {name}"

            if tid in track_boxes:
                bx1, by1, bx2, by2 = track_boxes[tid]
                face_h = int((by2 - by1) * 0.35)
                cv2.rectangle(vis, (bx1 + 3, by1 + 3), (bx2 - 3, by1 + face_h), (255, 255, 0), 1)

                (iw, ih), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
                cv2.rectangle(vis, (bx1, by2), (bx1 + iw + 6, by2 + 16), (30, 30, 30), -1)
                cv2.rectangle(vis, (bx1, by2), (bx1 + iw + 6, by2 + 16), (255, 255, 0), 1)
                cv2.putText(vis, badge, (bx1 + 3, by2 + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 0), 1, cv2.LINE_AA)

    # 4. Cross-Camera Re-ID Tag
    if context.reid_result and context.reid_result.global_entities:
        for entity in context.reid_result.global_entities:
            for b in entity.associated_tracks:
                if b.camera_id == camera_id and b.track_id in track_boxes:
                    bx1, by1, bx2, by2 = track_boxes[b.track_id]
                    reid_tag = f"Global: {entity.global_entity_id[-6:]}"
                    cv2.putText(vis, reid_tag, (bx1 + 3, by1 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 220, 255), 1, cv2.LINE_AA)

    # 5. Behavior & Loitering Indicators
    if context.behavior_result and context.behavior_result.observations:
        for obs in context.behavior_result.observations:
            if obs.track_id in track_boxes:
                bx1, by1, _, _ = track_boxes[obs.track_id]
                if obs.state.value == "loitering":
                    cv2.putText(vis, "! LOITERING !", (bx1 + 3, by1 + 42), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 255), 2, cv2.LINE_AA)
                elif obs.state.value == "dwelling":
                    cv2.putText(vis, "Dwelling", (bx1 + 3, by1 + 42), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 165, 255), 1, cv2.LINE_AA)

    # 6. Risk Alerts Badge (Top-Right)
    if context.risk_result and context.risk_result.assessments:
        max_assessment = max(context.risk_result.assessments, key=lambda a: a.severity_score, default=None)
        if max_assessment and max_assessment.severity_score >= 40.0:
            score = max_assessment.severity_score
            sev = max_assessment.severity.value.upper()
            risk_color = (0, 0, 255) if score >= 70.0 else (0, 165, 255)
            badge_text = f"RISK: {sev} ({score:.0f})"
            cv2.rectangle(vis, (w - 220, 44), (w - 16, 72), risk_color, -1)
            cv2.putText(vis, badge_text, (w - 208, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

    # 7. Diagnostic HUD (Bottom)
    hud_h = 48
    overlay_hud = vis.copy()
    cv2.rectangle(overlay_hud, (0, h - hud_h), (w, h), (14, 16, 20), -1)
    cv2.addWeighted(overlay_hud, 0.85, vis, 0.15, 0, vis)

    hud_text = f"FPS: {fps:>4.1f} | LATENCY: {latency_ms:>5.1f} ms | RES: {w}x{h}"
    cv2.putText(vis, hud_text, (14, h - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)

    st = context.stage_timings_ms
    stage_text = (
        f"Det: {st.get('detection', 0):.1f}ms | "
        f"Trk: {st.get('tracking', 0):.1f}ms | "
        f"Id: {st.get('identity', 0):.1f}ms | "
        f"ReID: {st.get('reid', 0):.1f}ms | "
        f"Beh: {st.get('behavior', 0):.1f}ms | "
        f"Risk: {st.get('risk', 0):.1f}ms"
    )
    cv2.putText(vis, stage_text, (14, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 210, 150), 1, cv2.LINE_AA)

    return vis


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> Optional[bytes]:
    """Encodes a BGR image frame to JPEG bytes."""
    params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    success, buffer = cv2.imencode(".jpg", frame, params)
    if success:
        return buffer.tobytes()
    return None
