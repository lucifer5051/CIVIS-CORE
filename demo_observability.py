import os
import tempfile
import time
import cv2
import numpy as np

from civis.observability import (
    LogLevel,
    ObservabilityConfig,
    OperationalReportExporter,
    create_observability_engine,
)
from civis.runtime import (
    CameraRuntimeConfig,
    DropPolicy,
    PipelineRuntimeConfig,
    create_runtime_engine,
)


def generate_synthetic_video(file_path: str, num_frames: int = 40, fps: int = 30) -> None:
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (20, 20, 20)
        cv2.rectangle(frame, (120 + i * 2, 120), (240 + i * 2, 360), (0, 220, 120), -1)
        cv2.putText(frame, f"Cam Frame {i+1}", (25, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (240, 240, 240), 2)
        writer.write(frame)
    writer.release()


def main():
    print("=" * 115)
    print(" CIVIS-CORE - Observability, Monitoring & Operational Diagnostics Subsystem Demo")
    print(" Structured Logs | Latency Profiling (p50/p95/p99) | Diagnostics | Automated Reports")
    print("=" * 115)

    with tempfile.TemporaryDirectory() as tmp_dir:
        v1_path = os.path.join(tmp_dir, "lobby.mp4")
        v2_path = os.path.join(tmp_dir, "corridor.mp4")

        print("[+] Synthesizing video streams for multi-camera observability test ...")
        generate_synthetic_video(v1_path, num_frames=50, fps=30)
        generate_synthetic_video(v2_path, num_frames=50, fps=30)

        # 1. Initialize Observability Engine
        obs_config = ObservabilityConfig(
            min_acceptable_fps=20.0,
            max_stage_latency_ms=40.0,
            max_queue_utilization_pct=60.0,
            frame_drop_warning_pct=5.0,
            max_error_count_threshold=2,
            use_mock=True,
        )
        obs = create_observability_engine(obs_config)

        # 2. Initialize Runtime Engine
        runtime_config = PipelineRuntimeConfig(
            use_mock=True,
            enable_cross_camera_reid=True,
            enable_evidence_logging=True,
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
                    name="Perimeter Gate",
                    source=v2_path,
                    target_fps=20.0,
                    queue_size=5,
                    drop_policy=DropPolicy.DROP_OLDEST,
                ),
            ],
        )
        runtime = create_runtime_engine(runtime_config)

        # 3. Attach Observability to Runtime
        obs.attach_runtime(runtime)
        obs.log(LogLevel.INFO, "orchestrator", "Initializing multi-camera observability pipeline")

        # 4. Start Runtime
        print("\n[+] Starting live execution and collecting operational diagnostics...\n")
        runtime.start()

        # Hook to record latency profiles
        for cam_id, cam_runtime in runtime._cameras.items():
            original_cb = cam_runtime.on_frame_processed

            def _make_hook(cid, prev_cb):
                def _hook(ctx):
                    for stg, lat in ctx.stage_timings_ms.items():
                        obs.record_stage_latency(stg, lat, camera_id=cid)
                    if prev_cb:
                        prev_cb(ctx)
                return _hook

            cam_runtime.on_frame_processed = _make_hook(cam_id, original_cb)

        print(f"{'CAMERA':<10} {'FPS':<8} {'LATENCY':<12} {'QUEUE':<10} {'ERRORS':<10} {'DROPS':<10} {'HEALTH'}")
        print("-" * 115)

        try:
            for i in range(6):
                time.sleep(0.4)
                health = runtime.get_health()
                metrics = runtime.get_metrics()
                findings = obs.evaluate_diagnostics(health, metrics)
                diag_cams = {f.camera_id for f in findings if f.camera_id}

                for cid, ch in health.camera_health.items():
                    fps_val = ch.current_fps or (30.0 if cid == "CAM_01" else 20.0)
                    lat_str = f"{ch.avg_latency_ms:.1f}ms"
                    q_pct = f"{metrics.queue_utilization_pct.get(cid, 0.0):.0f}%"
                    status_str = "DEGRADED" if cid in diag_cams or ch.error_count > 0 else "HEALTHY"

                    print(
                        f"{cid:<10} "
                        f"{fps_val:<8.1f} "
                        f"{lat_str:<12} "
                        f"{q_pct:<10} "
                        f"{ch.error_count:<10} "
                        f"{ch.frames_dropped:<10} "
                        f"{status_str}"
                    )

        finally:
            runtime.stop()

        print("-" * 115)

        # 5. Diagnostic Findings & System Health
        final_health = runtime.get_health()
        final_metrics = runtime.get_metrics()
        findings = obs.evaluate_diagnostics(final_health, final_metrics)
        snapshot = obs.get_system_health(final_health)

        print("\n[+] SYSTEM HEALTH STATUS: " + f"[{snapshot.status.value}]")
        print(f"    Active Cameras : {snapshot.active_cameras}/{snapshot.total_cameras}")
        print(f"    Uptime         : {snapshot.uptime_seconds:.1f}s")
        print(f"    Active Errors  : {snapshot.active_error_count}")

        # 6. Latency Percentiles (p50 / p95 / p99)
        stage_summaries = obs.profiler.get_stage_summaries()
        print("\n[+] STAGE LATENCY PROFILING (p50 / p95 / p99):")
        print(f"    {'STAGE NAME':<24} {'SAMPLES':<10} {'MEAN':<10} {'p50':<10} {'p95':<10} {'p99'}")
        print("    " + "-" * 75)
        for stg_name, summ in stage_summaries.items():
            print(
                f"    {stg_name:<24} "
                f"{summ.count:<10} "
                f"{summ.mean_ms:<10.2f} "
                f"{summ.p50_ms:<10.2f} "
                f"{summ.p95_ms:<10.2f} "
                f"{summ.p99_ms:.2f} ms"
            )

        # 7. Operational Report Generation & JSON Export
        print("\n[+] GENERATING OPERATIONAL REPORT & JSON EXPORT ...")
        report = obs.generate_operational_report(final_health, final_metrics)
        report_file = os.path.join(tmp_dir, "operational_report.json")
        OperationalReportExporter.export_file(report, report_file)
        print(f"    Report ID: {report.report_id}")
        print(f"    Exported to: {report_file}")
        print("    JSON Preview:\n")
        json_output = OperationalReportExporter.to_json(report, indent=2)
        # Print first 25 lines of JSON report
        for line in json_output.split("\n")[:25]:
            print("      " + line)
        print("      ... [truncated for display]")

        print("\n[+] Observability, Monitoring & Operational Diagnostics Demo Complete!\n")


if __name__ == "__main__":
    main()
