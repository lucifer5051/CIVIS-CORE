"""
Observability, Monitoring & Operational Diagnostics Subsystem for CIVIS.
"""

from civis.observability.base import BaseObservabilityEngine
from civis.observability.diagnostics import DiagnosticEngine
from civis.observability.engine import MockObservabilityEngine, ObservabilityEngine
from civis.observability.exporter import OperationalReportExporter
from civis.observability.factory import create_observability_engine
from civis.observability.health import SystemHealthAggregator
from civis.observability.logging import StructuredLogger
from civis.observability.metrics import Counter, Gauge, Histogram, MetricsRegistry
from civis.observability.models import (
    DiagnosticFinding,
    DiagnosticSeverity,
    ErrorRecord,
    LatencySummary,
    LogLevel,
    LogRecord,
    ObservabilityConfig,
    OperationalReport,
    SystemHealthSnapshot,
    SystemHealthStatus,
)
from civis.observability.profiler import PipelineProfiler

__all__ = [
    "LogLevel",
    "DiagnosticSeverity",
    "SystemHealthStatus",
    "LogRecord",
    "LatencySummary",
    "DiagnosticFinding",
    "ErrorRecord",
    "SystemHealthSnapshot",
    "OperationalReport",
    "ObservabilityConfig",
    "BaseObservabilityEngine",
    "StructuredLogger",
    "Counter",
    "Gauge",
    "Histogram",
    "MetricsRegistry",
    "PipelineProfiler",
    "DiagnosticEngine",
    "SystemHealthAggregator",
    "OperationalReportExporter",
    "ObservabilityEngine",
    "MockObservabilityEngine",
    "create_observability_engine",
]
