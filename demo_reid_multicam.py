import os
import tempfile
import time
import cv2
import numpy as np

from civis.detection import DetectorConfig, create_detector
from civis.ingestion import CameraConfig, CameraStatus, SourceType, StreamManager
from civis.reid import (
    CameraTopologyConstraint,
    ReIDEngineConfig,
    create_cross_camera_reid_engine,
)
from civis.tracking import TrackerConfig, create_tracker


def generate_multicam_videos(cam1_path: str, cam2_path: str, num_frames: int = 20, fps: int = 10) -> None:
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    # Camera 1 (Lobby): Person in red jacket moves across lobby in first half
    w1 = cv2.VideoWriter(cam1_path, fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (35, 35, 35)
        cv2.putText(frame, "CAM 01: LOBBY ENTRANCE", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 200, 100), 2)
        if i < 15:
            # Person moving
            x = 80 + i * 20
            # Red jacket person
            cv2.rectangle(frame, (x, 120), (x + 90, 380), (30, 40, 200), -1)
            cv2.putText(frame, "Target A", (x, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        w1.write(frame)
    w1.release()

    # Camera 2 (Corridor): Person in same red jacket enters corridor in second half
    w2 = cv2.VideoWriter(cam2_path, fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (25, 25, 25)
        cv2.putText(frame, "CAM 02: RESTRICTED CORRIDOR", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 220), 2)
        if i >= 5:
            # Person enters corridor after 0.5s transition
            x = 100 + (i - 5) * 18
            # Same red jacket person
            cv2.rectangle(frame, (x, 130), (x + 90, 390), (30, 40, 200), -1)
            cv2.putText(frame, "Target A (Re-Entry)", (x, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        w2.write(frame)
    w2.release()


def main():
    print("=" * 110)
    print(" CIVIS-CORE - Cross-Camera Person Re-Identification & Global Entity Tracking Demo")
    print("=" * 110)

    with tempfile.TemporaryDirectory() as tmp:
        cam1_video = os.path.join(tmp, "cam1_lobby.mp4")
        cam2_video = os.path.join(tmp, "cam2_corridor.mp4")

        print("[+] Synthesizing 2-camera synchronized surveillance video feeds ...")
        generate_multicam_videos(cam1_video, cam2_video, num_frames=20, fps=10)

        # 1. Multi-Camera Stream Manager
        manager = StreamManager()
        manager.add_camera(CameraConfig(
            camera_id="CAM_LOBBY",
            name="Lobby Entrance",
            source_type=SourceType.FILE,
            source=cam1_video,
            loop_file=False,
            fps_limit=10.0,
        ))
        manager.add_camera(CameraConfig(
            camera_id="CAM_CORRIDOR",
            name="Restricted Corridor",
            source_type=SourceType.FILE,
            source=cam2_video,
            loop_file=False,
            fps_limit=10.0,
        ))

        # 2. Shared AI Subsystems
        detector = create_detector(DetectorConfig(use_mock=True))
        tracker_lobby = create_tracker(TrackerConfig(use_mock=True))
        tracker_corridor = create_tracker(TrackerConfig(use_mock=True))

        # 3. Cross-Camera Re-ID Engine with Topology Gating
        reid_config = ReIDEngineConfig(
            use_mock=True,
            similarity_threshold=0.65,
            topology_constraints=[
                CameraTopologyConstraint(
                    source_camera_id="CAM_LOBBY",
                    target_camera_id="CAM_CORRIDOR",
                    min_travel_time_sec=0.0,
                    max_travel_time_sec=60.0,
                    allow_bidirectional=True,
                )
            ],
            gallery_ttl_seconds=60.0,
        )
        reid_engine = create_cross_camera_reid_engine(reid_config)

        print("[+] Multi-Camera pipeline initialized. Starting concurrent streams...\n")
        manager.start_all()
        time.sleep(0.3)

        header = f"{'FRAME':<6} | {'CAM_LOBBY TRACKS':<18} | {'CAM_CORRIDOR TRACKS':<20} | {'CROSS-CAM MATCH':<25} | {'GLOBAL ENTITIES'}"
        print(header)
        print("-" * 110)

        total_frames = 0
        total_cross_matches = 0

        try:
            while True:
                p1 = manager.read_frame("CAM_LOBBY", timeout=0.2)
                p2 = manager.read_frame("CAM_CORRIDOR", timeout=0.2)

                if p1 is None and p2 is None:
                    if (
                        manager.get_status("CAM_LOBBY") in (CameraStatus.DISCONNECTED, CameraStatus.STOPPED)
                        and manager.get_status("CAM_CORRIDOR") in (CameraStatus.DISCONNECTED, CameraStatus.STOPPED)
                    ):
                        break
                    continue

                total_frames += 1
                frame_packets = {}
                track_results = {}

                if p1 is not None:
                    frame_packets["CAM_LOBBY"] = p1
                    det1 = detector.detect(p1)
                    track_results["CAM_LOBBY"] = tracker_lobby.update(det1)

                if p2 is not None:
                    frame_packets["CAM_CORRIDOR"] = p2
                    det2 = detector.detect(p2)
                    track_results["CAM_CORRIDOR"] = tracker_corridor.update(det2)

                reid_result = reid_engine.process(frame_packets, track_results)

                # Format log row
                t1_str = f"{len(track_results.get('CAM_LOBBY', type('', (), {'tracks': []})).tracks)} tracks"
                t2_str = f"{len(track_results.get('CAM_CORRIDOR', type('', (), {'tracks': []})).tracks)} tracks"

                match_strs = []
                for m in reid_result.active_matches:
                    match_strs.append(f"{m.query_camera_id}#T{m.query_track_id} <-> {m.matched_camera_id}#T{m.matched_track_id} ({m.similarity_score:.2f})")
                    total_cross_matches += 1

                global_ent_strs = [
                    f"{e.global_entity_id} ({e.num_associated_cameras} cams)"
                    for e in reid_result.global_entities
                ]

                print(
                    f"{total_frames:<6} | "
                    f"{t1_str:<18} | "
                    f"{t2_str:<20} | "
                    f"{', '.join(match_strs) if match_strs else '-':<25} | "
                    f"{', '.join(global_ent_strs) if global_ent_strs else '-'}"
                )

                for m in reid_result.active_matches:
                    print(f"\n  [LINK] >>> CROSS-CAMERA PERSON RE-ID CONFIRMED <<<")
                    print(f"  Target linked between {m.query_camera_id} (Track #{m.query_track_id}) and {m.matched_camera_id} (Track #{m.matched_track_id})")
                    print(f"  Similarity Score: {m.similarity_score:.4f} | Time Delta: {m.time_delta_seconds:.2f}s | Global Entity: {m.global_entity_id}\n")

        finally:
            manager.stop_all()

        print("-" * 110)
        print(f"\n[+] Multi-Camera Re-ID Demo Completed. Total Frames: {total_frames}, Cross-Camera Re-ID Matches: {total_cross_matches}.\n")


if __name__ == "__main__":
    main()
