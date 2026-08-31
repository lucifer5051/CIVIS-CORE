import numpy as np

from civis.detection.factory import create_detector
from civis.detection.models import BoundingBox, DetectionMode, DetectorConfig, SAHIConfig
from civis.identity.face_detector import MockFaceDetector, YuNetFaceDetector
from civis.identity.models import FaceDetectorConfig, IdentityConfig, IdentityState
from civis.identity.factory import create_identity_engine
from civis.ingestion.models import FramePacket
from civis.tracking.models import TrackResult, TrackedObject, TrackState


def main():
    print("=" * 115)
    print(" CIVIS-CORE - Object & Face Detection Enhancement Demo")
    print(" SAHI Adaptive Small-Object Inference | OpenCV YuNet Face Detection | 5 Keypoints | Track Association")
    print("=" * 115)

    # 1. Normal vs Small/Distant Object Detection with SAHI AUTO Mode
    print("\n[+] 1. Testing Small/Distant Object Detection with Adaptive Tiling...")
    sahi_cfg = SAHIConfig(
        slice_height=320,
        slice_width=320,
        mode=DetectionMode.AUTO,
        auto_min_dimension=960,
    )
    det_cfg = DetectorConfig(use_mock=True, sahi_config=sahi_cfg)
    detector = create_detector(det_cfg)

    # High-resolution frame simulating distant surveillance camera
    high_res_frame = np.ones((1080, 1920, 3), dtype=np.uint8) * 100
    pkt = FramePacket.create(camera_id="CAM_HIGH_RES_01", frame_number=1, frame=high_res_frame)

    det_result = detector.detect(pkt)
    print(f"    Frame Resolution        : {pkt.dimensions[0]}x{pkt.dimensions[1]}")
    print(f"    Configured SAHI Mode    : {det_result.metadata.get('configured_mode')}")
    print(f"    Resolved Slicing Action : {det_result.metadata.get('sahi_mode')}")
    print(f"    Slice Count Dispatched  : {det_result.metadata.get('slice_count')}")
    print(f"    Detections Identified   : {det_result.num_detections} targets")
    for i, d in enumerate(det_result.detections[:3]):
        print(f"      * Target #{i+1}: {d.class_name:<10} | Conf: {d.confidence:.2f} | BBox: [{d.bbox.x1:.1f}, {d.bbox.y1:.1f}, {d.bbox.x2:.1f}, {d.bbox.y2:.1f}]")

    # 2. Specialized Face Detection with 5 Facial Keypoints
    print("\n[+] 2. Evaluating Specialized Face Detection Engine...")
    face_detector = MockFaceDetector()
    track1 = TrackedObject(
        track_id=1,
        class_id=0,
        class_name="person",
        confidence=0.92,
        bbox=BoundingBox(x1=200.0, y1=150.0, x2=380.0, y2=600.0),
        state=TrackState.TRACKED,
    )
    track2 = TrackedObject(
        track_id=2,
        class_id=0,
        class_name="person",
        confidence=0.88,
        bbox=BoundingBox(x1=600.0, y1=180.0, x2=760.0, y2=580.0),
        state=TrackState.TRACKED,
    )
    track_result = TrackResult(
        camera_id="CAM_HIGH_RES_01",
        frame_id=pkt.frame_id,
        timestamp=pkt.timestamp,
        frame_number=1,
        dimensions=pkt.dimensions,
        tracks=[track1, track2],
        active_track_ids=[1, 2],
    )

    face_crops = face_detector.detect_faces(pkt, track_result)
    print(f"    Total Tracked People    : {len(track_result.tracks)}")
    print(f"    Detected Facial Crops   : {len(face_crops)}")
    for crop in face_crops:
        print(f"      * Track #{crop.track_id} -> Face ID: {crop.face_id} | Face BBox: [{crop.face_bbox.x1:.1f}, {crop.face_bbox.y1:.1f}, {crop.face_bbox.x2:.1f}, {crop.face_bbox.y2:.1f}]")
        if crop.landmarks:
            print(f"        5-Point Landmarks: RightEye={crop.landmarks[0]}, LeftEye={crop.landmarks[1]}, Nose={crop.landmarks[2]}")

    # 3. Downstream Identity Association Integration
    print("\n[+] 3. Downstream Multi-Signal Identity Association Verification...")
    id_cfg = IdentityConfig(use_mock=True, min_observations=1)
    id_engine = create_identity_engine(id_cfg)
    id_result = id_engine.process(pkt, track_result)

    print(f"    Associated Identities   : {len(id_result.identities)}")
    for id_entry in id_result.identities:
        print(f"      * Track #{id_entry.track_id} -> Identity: '{id_entry.name}' (State: {id_entry.state.value.upper()}, Conf: {id_entry.recognition_confidence:.2f})")

    print("\n[+] Object & Face Detection Demonstration Complete!\n")


if __name__ == "__main__":
    main()
