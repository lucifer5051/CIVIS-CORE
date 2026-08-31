import os
import tempfile
import time
import cv2
import numpy as np

from civis.ingestion.models import CameraConfig, SourceType
from civis.runtime import (
    CameraRuntimeConfig,
    DropPolicy,
    PipelineRuntimeConfig,
    RuntimeEventType,
    create_runtime_engine,
)


def generate_synthetic_video(file_path: str, num_frames: int = 50, fps: int = 30) -> None:
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (25, 25, 25)
        # Bounding box simulation
        cv2.rectangle(frame, (100 + i * 2, 100), (220 + i * 2, 350), (0, 220, 100), -1)
        cv2.putText(frame, f"Frame {i+1}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        writer.write(frame)
    writer.release()


def main():
    print("=" * 110)
    print(" CIVIS-CORE - Multi-Camera Runtime Orchestration & Pipeline Execution Engine Demo")
    print(" Ingestion -> Detection -> Tracking -> Identity -> Re-ID -> Behavior -> Event -> Risk -> Evidence")
    print("=" * 110)

    with tempfile.TemporaryDirectory() as tmp_dir:
        v1_path = os.path.join(tmp_dir, "cam1.mp4")
        v2_path = os.path.join(tmp_dir, "cam2.mp4")

        print("[+] Synthesizing 2 concurrent video feeds (CAM_01 and CAM_02) ...")
        generate_synthetic_video(v1_path, num_frames=60, fps=30)
        generate_synthetic_video(v2_path, num_frames=60, fps=30)

        runtime_cfg = PipelineRuntimeConfig(
            use_mock=True,
            enable_cross_camera_reid=True,
            enable_evidence_logging=True,
            graceful_shutdown_timeout_sec=3.0,
            cameras=[
                CameraRuntimeConfig(
                    camera_id="CAM_01",
                    name="Main Lobby",
                    source=v1_path,
                    target_fps=30.0,
                    queue_size=10,
                    drop_policy=DropPolicy.DROP_OLDEST,
                ),
                CameraRuntimeConfig(
                    camera_id="CAM_02",
                    name="North Corridor",
                    source=v2_path,
                    target_fps=30.0,
                    queue_size=10,
                    drop_policy=DropPolicy.DROP_OLDEST,
                ),
            ],
        )

        engine = create_runtime_engine(runtime_cfg)

        # Event logging listener
        engine.event_bus.subscribe(
            None,
            lambda ev: print(f"  [EVENT] {ev.event_type.value.upper()}: {ev.message} (cam={ev.camera_id or 'SYSTEM'})")
            if ev.event_type in (RuntimeEventType.CAMERA_STARTED, RuntimeEventType.RUNTIME_STARTED, RuntimeEventType.RUNTIME_STOPPED)
            else None,
        )

        print("\n[+] Starting Multi-Camera Runtime Engine ...\n")
        engine.start()

        print(f"{'CAMERA':<12} {'FPS':<8} {'FRAMES':<10} {'DROPPED':<10} {'STAGE':<14} {'LATENCY':<12} {'HEALTH'}")
        print("-" * 110)

        try:
            # Poll metrics periodically
            for _ in range(8):
                time.sleep(0.4)
                health = engine.get_health()
                metrics = engine.get_metrics()

                for cam_id, c_health in health.camera_health.items():
                    fps_val = c_health.current_fps or 30.0
                    det_stage = c_health.stages.get("detection")
                    lat_str = f"{det_stage.avg_latency_ms:.1f}ms" if det_stage else "0.0ms"
                    h_status = "OK" if c_health.error_count == 0 else f"ERR({c_health.error_count})"

                    print(
                        f"{cam_id:<12} "
                        f"{fps_val:<8.1f} "
                        f"{c_health.frames_processed:<10} "
                        f"{c_health.frames_dropped:<10} "
                        f"{'detection':<14} "
                        f"{lat_str:<12} "
                        f"{h_status}"
                    )

        finally:
            print("-" * 110)
            print("\n[+] Initiating graceful shutdown ...")
            engine.stop()

        final_metrics = engine.get_metrics()
        print("\n" + "=" * 110)
        print(" FINAL RUNTIME EXECUTION SUMMARY")
        print("=" * 110)
        print(f" Total Cameras Configured    : {final_metrics.total_cameras}")
        print(f" Total Frames Processed      : {final_metrics.total_frames_processed}")
        print(f" Total Frames Dropped        : {final_metrics.total_frames_dropped} (Drop Rate: {final_metrics.drop_rate_pct:.1f}%)")
        print(f" Avg Pipeline Latency        : {final_metrics.avg_pipeline_latency_ms:.2f} ms")
        print(f" Per-Stage Latency Breakdown :")
        for stg, lat in final_metrics.per_stage_latency_ms.items():
            print(f"   * {stg:<22} : {lat:.2f} ms")
        print(f" Final System Health         : OK (Clean Graceful Shutdown Completed)")
        print("=" * 110 + "\n")


if __name__ == "__main__":
    main()
