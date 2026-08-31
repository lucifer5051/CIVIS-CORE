"""
CIVIS-CORE Deterministic Performance & Reliability Benchmark
Measures multi-camera throughput, per-stage latency distribution, frame drops, and memory stability.
"""

import os
import sys
import time
import tracemalloc
from typing import Any, Dict, List
import numpy as np

from civis.detection.models import DetectionMode, DetectorConfig, SAHIConfig
from civis.ingestion.models import FramePacket
from civis.runtime.engine import MockRuntimeEngine
from civis.runtime.models import (
    CameraRuntimeConfig,
    DropPolicy,
    PipelineRuntimeConfig,
    StageConfig,
)


def make_synthetic_packet(camera_id: str, frame_num: int, width: int = 640, height: int = 480) -> FramePacket:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Add a synthetic high-contrast rectangle to simulate detection target
    x1, y1 = 100 + (frame_num % 50), 100 + (frame_num % 30)
    img[y1:y1 + 80, x1:x1 + 60] = [200, 200, 200]
    return FramePacket.create(
        camera_id=camera_id,
        frame_number=frame_num,
        frame=img,
        timestamp=time.time(),
    )


def run_benchmark_configuration(
    num_cameras: int = 1,
    num_frames: int = 50,
    sahi_mode: DetectionMode = DetectionMode.FULL_FRAME,
) -> Dict[str, Any]:
    tracemalloc.start()
    start_mem, _ = tracemalloc.get_traced_memory()

    cams = [
        CameraRuntimeConfig(
            camera_id=f"CAM_{i+1:02d}",
            queue_size=20,
            drop_policy=DropPolicy.DROP_OLDEST,
        )
        for i in range(num_cameras)
    ]

    stages_cfg = {
        "detection": StageConfig(name="detection", enabled=True),
        "tracking": StageConfig(name="tracking", enabled=True),
        "identity": StageConfig(name="identity", enabled=True),
        "reid": StageConfig(name="reid", enabled=True),
        "behavior": StageConfig(name="behavior", enabled=True),
        "event_intelligence": StageConfig(name="event_intelligence", enabled=True),
        "risk": StageConfig(name="risk", enabled=True),
        "evidence": StageConfig(name="evidence", enabled=True),
    }

    config = PipelineRuntimeConfig(
        use_mock=True,
        cameras=cams,
        stages=stages_cfg,
        enable_cross_camera_reid=True,
        enable_evidence_logging=True,
    )

    runtime = MockRuntimeEngine(config)

    # Configure SAHI mode on detection stage if requested
    for cam_id in [c.camera_id for c in cams]:
        cam_rt = runtime.get_camera_runtime(cam_id)
        if cam_rt and sahi_mode != DetectionMode.FULL_FRAME:
            from civis.detection.factory import create_detector
            from civis.detection.sahi_detector import SAHIDetector
            base_det = create_detector(DetectorConfig(use_mock=True))
            sahi_det = SAHIDetector(base_det, SAHIConfig(mode=sahi_mode, slice_height=256, slice_width=256))
            cam_rt.pipeline.stages[0].detector = sahi_det

    t_start = time.perf_counter()

    # Process sequential frames through camera pipelines synchronously to measure core execution
    total_processed = 0
    stage_latencies: Dict[str, List[float]] = {}

    for f_idx in range(num_frames):
        for cam_cfg in cams:
            cam_id = cam_cfg.camera_id
            pkt = make_synthetic_packet(cam_id, f_idx + 1)
            cam_rt = runtime.get_camera_runtime(cam_id)
            ctx = cam_rt.process_frame_sync(pkt)
            total_processed += 1
            for sname, lat in ctx.stage_timings_ms.items():
                stage_latencies.setdefault(sname, []).append(lat)

    t_total = time.perf_counter() - t_start
    fps = total_processed / t_total if t_total > 0 else 0.0

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    health = runtime.get_health()

    # Verify ledger integrity
    evidence_valid = True
    if runtime.evidence_engine:
        evidence_valid, _ = runtime.evidence_engine.verify_ledger_integrity()

    # Calculate percentiles per stage
    stage_summary = {}
    for sname, lats in stage_latencies.items():
        arr = np.array(lats, dtype=np.float64)
        stage_summary[sname] = {
            "mean_ms": round(float(np.mean(arr)), 2),
            "p50_ms": round(float(np.percentile(arr, 50)), 2),
            "p95_ms": round(float(np.percentile(arr, 95)), 2),
            "p99_ms": round(float(np.percentile(arr, 99)), 2),
        }

    return {
        "num_cameras": num_cameras,
        "num_frames_per_camera": num_frames,
        "total_frames": total_processed,
        "total_time_seconds": round(t_total, 3),
        "throughput_fps": round(fps, 1),
        "peak_memory_mb": round(peak_mem / (1024 * 1024), 2),
        "net_memory_delta_mb": round((current_mem - start_mem) / (1024 * 1024), 2),
        "total_errors": health.total_errors,
        "evidence_integrity_valid": evidence_valid,
        "stage_latency_percentiles": stage_summary,
    }


def main():
    print("=" * 78)
    print(" CIVIS-CORE SUBSYSTEM BENCHMARK & RELIABILITY VERIFICATION")
    print("=" * 78)

    configs = [
        ("Single Camera (Standard)", 1, 50, DetectionMode.FULL_FRAME),
        ("Dual Camera (Standard)", 2, 50, DetectionMode.FULL_FRAME),
        ("Quad Camera (Standard)", 4, 50, DetectionMode.FULL_FRAME),
        ("Dual Camera (Adaptive SAHI)", 2, 50, DetectionMode.ADAPTIVE),
    ]

    results = []
    all_passed = True

    for label, num_cams, num_frames, mode in configs:
        print(f"\n[*] Running: {label} ({num_cams} cameras, {num_frames} frames/cam)...")
        res = run_benchmark_configuration(num_cams, num_frames, mode)
        results.append((label, res))

        print(f"    -> FPS: {res['throughput_fps']} fps | Latency: {res['total_time_seconds']}s")
        print(f"    -> Peak Memory: {res['peak_memory_mb']} MB | Errors: {res['total_errors']}")
        print(f"    -> Forensic Lineage Integrity: {'VALID' if res['evidence_integrity_valid'] else 'FAILED'}")

        if not res["evidence_integrity_valid"] or res["total_errors"] > 0:
            all_passed = False

    print("\n" + "=" * 78)
    print(f"{'Configuration':<30} | {'FPS':<8} | {'Peak MB':<8} | {'Errors':<8} | {'Integrity':<10}")
    print("-" * 78)
    for label, res in results:
        integ = "VALID" if res["evidence_integrity_valid"] else "FAIL"
        print(f"{label:<30} | {res['throughput_fps']:<8.1f} | {res['peak_memory_mb']:<8.2f} | {res['total_errors']:<8} | {integ:<10}")
    print("=" * 78)

    # Detailed per-stage breakdown for the 4-camera run
    quad_res = results[2][1]
    print("\nStage Latency Breakdown (Quad Camera):")
    print(f"{'Stage':<20} | {'Mean (ms)':<10} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'p99 (ms)':<10}")
    print("-" * 68)
    for stage_name, lat in quad_res["stage_latency_percentiles"].items():
        print(f"{stage_name:<20} | {lat['mean_ms']:<10.2f} | {lat['p50_ms']:<10.2f} | {lat['p95_ms']:<10.2f} | {lat['p99_ms']:<10.2f}")
    print("=" * 78)

    if not all_passed:
        print("\n[!] Benchmark failed verification checks.")
        sys.exit(1)
    else:
        print("\n[+] All benchmark configurations and cryptographic checks PASSED.")
        sys.exit(0)


if __name__ == "__main__":
    main()
