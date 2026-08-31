from collections import deque
import threading
from typing import Any, Dict, List, Optional
import numpy as np

from civis.observability.models import LatencySummary


class Counter:
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._value: float = 0.0
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    @property
    def value(self) -> float:
        with self._lock:
            return self._value

    def reset(self) -> None:
        with self._lock:
            self._value = 0.0


class Gauge:
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._value: float = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    @property
    def value(self) -> float:
        with self._lock:
            return self._value

    def reset(self) -> None:
        with self._lock:
            self._value = 0.0


class Histogram:
    """
    Sliding-window sample histogram providing exact p50, p95, p99 percentiles.
    """

    def __init__(self, name: str, max_samples: int = 200, description: str = "") -> None:
        self.name = name
        self.max_samples = max_samples
        self.description = description
        self._samples: deque = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        self._total_count: int = 0

    def observe(self, value: float) -> None:
        with self._lock:
            self._samples.append(float(value))
            self._total_count += 1

    def get_summary(self) -> LatencySummary:
        with self._lock:
            if not self._samples:
                return LatencySummary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

            arr = np.array(self._samples, dtype=np.float64)
            cnt = self._total_count
            min_val = float(np.min(arr))
            max_val = float(np.max(arr))
            mean_val = float(np.mean(arr))
            p50 = float(np.percentile(arr, 50))
            p95 = float(np.percentile(arr, 95))
            p99 = float(np.percentile(arr, 99))

            return LatencySummary(
                count=cnt,
                min_ms=round(min_val, 2),
                max_ms=round(max_val, 2),
                mean_ms=round(mean_val, 2),
                p50_ms=round(p50, 2),
                p95_ms=round(p95, 2),
                p99_ms=round(p99, 2),
            )

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()
            self._total_count = 0


class MetricsRegistry:
    """
    In-process thread-safe metric repository.
    """

    def __init__(self, default_sample_size: int = 200) -> None:
        self.default_sample_size = default_sample_size
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._lock = threading.Lock()

    def counter(self, name: str, description: str = "") -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, description)
            return self._counters[name]

    def gauge(self, name: str, description: str = "") -> Gauge:
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, description)
            return self._gauges[name]

    def histogram(self, name: str, max_samples: Optional[int] = None, description: str = "") -> Histogram:
        with self._lock:
            if name not in self._histograms:
                sz = max_samples or self.default_sample_size
                self._histograms[name] = Histogram(name, max_samples=sz, description=description)
            return self._histograms[name]

    def get_all_metrics(self) -> Dict[str, Any]:
        with self._lock:
            counters = {name: c.value for name, c in self._counters.items()}
            gauges = {name: g.value for name, g in self._gauges.items()}
            histograms = {name: h.get_summary().__dict__ for name, h in self._histograms.items()}
            return {
                "counters": counters,
                "gauges": gauges,
                "histograms": histograms,
            }

    def reset(self) -> None:
        with self._lock:
            for c in self._counters.values():
                c.reset()
            for g in self._gauges.values():
                g.reset()
            for h in self._histograms.values():
                h.reset()
