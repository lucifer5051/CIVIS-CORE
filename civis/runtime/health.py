import time
from typing import Dict, List, Optional
from collections import deque

from civis.runtime.models import (
    CameraHealth,
    RuntimeHealth,
    RuntimeMetrics,
    RuntimeState,
    StageHealth,
    StageState,
)


class RollingStats:
    """Computes rolling averages and FPS with bounded memory window."""

    def __init__(self, window_size: int = 30) -> None:
        self.window_size = window_size
        self._latencies: deque = deque(maxlen=window_size)
        self._timestamps: deque = deque(maxlen=window_size)

    def record(self, latency_ms: float, timestamp: Optional[float] = None) -> None:
        ts = timestamp if timestamp is not None else time.time()
        self._latencies.append(latency_ms)
        self._timestamps.append(ts)

    @property
    def avg_latency(self) -> float:
        if not self._latencies:
            return 0.0
        return sum(self._latencies) / len(self._latencies)

    @property
    def fps(self) -> float:
        if len(self._timestamps) < 2:
            return 0.0
        dt = self._timestamps[-1] - self._timestamps[0]
        if dt <= 0:
            return 0.0
        return (len(self._timestamps) - 1) / dt


class HealthMonitor:
    """
    Manages structured health tracking for stages, cameras, and runtime.
    """

    def __init__(self) -> None:
        self._stage_stats: Dict[str, Dict[str, RollingStats]] = {}  # camera_id -> stage_name -> RollingStats
        self._camera_stats: Dict[str, RollingStats] = {}             # camera_id -> RollingStats
        self._start_time: float = time.time()

    def record_stage_execution(
        self,
        camera_id: str,
        stage_name: str,
        latency_ms: float,
        is_error: bool = False,
        error_msg: Optional[str] = None,
    ) -> None:
        if camera_id not in self._stage_stats:
            self._stage_stats[camera_id] = {}
        if stage_name not in self._stage_stats[camera_id]:
            self._stage_stats[camera_id][stage_name] = RollingStats()

        stats = self._stage_stats[camera_id][stage_name]
        stats.record(latency_ms)

    def record_frame_processed(self, camera_id: str, total_latency_ms: float) -> None:
        if camera_id not in self._camera_stats:
            self._camera_stats[camera_id] = RollingStats()
        self._camera_stats[camera_id].record(total_latency_ms)

    def get_camera_fps(self, camera_id: str) -> float:
        if camera_id in self._camera_stats:
            return round(self._camera_stats[camera_id].fps, 1)
        return 0.0

    def get_camera_avg_latency(self, camera_id: str) -> float:
        if camera_id in self._camera_stats:
            return round(self._camera_stats[camera_id].avg_latency, 2)
        return 0.0

    def get_stage_avg_latency(self, camera_id: str, stage_name: str) -> float:
        if camera_id in self._stage_stats and stage_name in self._stage_stats[camera_id]:
            return round(self._stage_stats[camera_id][stage_name].avg_latency, 2)
        return 0.0
