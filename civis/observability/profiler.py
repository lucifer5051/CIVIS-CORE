import contextlib
import time
from typing import Dict, Iterator, Optional

from civis.observability.metrics import MetricsRegistry
from civis.observability.models import LatencySummary


class PipelineProfiler:
    """
    Lightweight latency profiling manager providing percentiles (p50, p95, p99)
    across all stages and cameras.
    """

    def __init__(self, registry: MetricsRegistry) -> None:
        self.registry = registry

    @contextlib.contextmanager
    def time_stage(self, stage_name: str, camera_id: Optional[str] = None) -> Iterator[None]:
        start_t = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            self.record_latency(stage_name, elapsed_ms, camera_id)

    def record_latency(self, stage_name: str, latency_ms: float, camera_id: Optional[str] = None) -> None:
        # Global stage metric
        self.registry.histogram(f"stage_latency_ms_{stage_name}").observe(latency_ms)

        # Per-camera stage metric if camera_id provided
        if camera_id:
            self.registry.histogram(f"cam_{camera_id}_stage_{stage_name}_ms").observe(latency_ms)

    def record_pipeline_latency(self, latency_ms: float, camera_id: Optional[str] = None) -> None:
        self.registry.histogram("pipeline_end_to_end_ms").observe(latency_ms)
        if camera_id:
            self.registry.histogram(f"cam_{camera_id}_end_to_end_ms").observe(latency_ms)

    def get_stage_summaries(self) -> Dict[str, LatencySummary]:
        summaries: Dict[str, LatencySummary] = {}
        prefix = "stage_latency_ms_"
        for name, h in self.registry._histograms.items():
            if name.startswith(prefix):
                stage_name = name[len(prefix):]
                summaries[stage_name] = h.get_summary()
        return summaries

    def get_summary(self, metric_name: str) -> LatencySummary:
        h = self.registry.histogram(metric_name)
        return h.get_summary()
