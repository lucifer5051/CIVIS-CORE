import json
import time
import unittest

from civis.observability import (
    DiagnosticFinding,
    DiagnosticSeverity,
    Histogram,
    LogLevel,
    MetricsRegistry,
    ObservabilityConfig,
    OperationalReportExporter,
    StructuredLogger,
    SystemHealthAggregator,
    SystemHealthStatus,
    create_observability_engine,
)
from civis.runtime.models import (
    CameraHealth,
    CameraRuntimeConfig,
    PipelineRuntimeConfig,
    RuntimeHealth,
    RuntimeMetrics,
    RuntimeState,
    StageHealth,
    StageState,
)
from civis.runtime import create_runtime_engine


class TestObservabilitySubsystem(unittest.TestCase):

    def test_structured_logging(self):
        """Test structured logging with severity levels and metadata."""
        logger = StructuredLogger(max_buffer_size=10)

        logger.debug("test_comp", "Debug msg", camera_id="CAM_01")
        logger.info("test_comp", "Info msg", camera_id="CAM_01")
        logger.warning("test_comp", "Warning msg", camera_id="CAM_02")
        logger.error("test_comp", "Error msg", camera_id="CAM_01", error_details="SyntaxError")

        logs = logger.get_logs()
        self.assertEqual(len(logs), 4)

        cam1_logs = logger.get_logs(camera_id="CAM_01")
        self.assertEqual(len(cam1_logs), 3)

        warn_logs = logger.get_logs(min_level=LogLevel.WARNING)
        self.assertEqual(len(warn_logs), 2)

        err_dict = logs[-1].to_dict()
        self.assertEqual(err_dict["level"], "ERROR")
        self.assertEqual(err_dict["error_details"], "SyntaxError")

    def test_metric_counters_and_gauges(self):
        """Test metric registry counters and gauges."""
        registry = MetricsRegistry()
        c = registry.counter("test_counter")
        g = registry.gauge("test_gauge")

        c.inc(5.0)
        c.inc(2.0)
        self.assertEqual(c.value, 7.0)

        g.set(42.5)
        self.assertEqual(g.value, 42.5)

        metrics = registry.get_all_metrics()
        self.assertEqual(metrics["counters"]["test_counter"], 7.0)
        self.assertEqual(metrics["gauges"]["test_gauge"], 42.5)

    def test_latency_histogram_percentiles_and_rolling_bounds(self):
        """Test Histogram percentile calculations (p50, p95, p99) and sample bounds."""
        hist = Histogram("test_lat", max_samples=100)

        # Feed numbers 1 to 100
        for i in range(1, 101):
            hist.observe(float(i))

        summary = hist.get_summary()
        self.assertEqual(summary.count, 100)
        self.assertEqual(summary.min_ms, 1.0)
        self.assertEqual(summary.max_ms, 100.0)
        self.assertAlmostEqual(summary.p50_ms, 50.5, delta=1.0)
        self.assertAlmostEqual(summary.p95_ms, 95.05, delta=1.5)
        self.assertAlmostEqual(summary.p99_ms, 99.01, delta=1.5)

        # Feed 50 more values and assert bounded size
        for i in range(101, 151):
            hist.observe(float(i))

        self.assertEqual(len(hist._samples), 100)
        self.assertEqual(hist._total_count, 150)

    def test_repeated_error_aggregation(self):
        """Test repeated error tracking without duplicate log storms."""
        engine = create_observability_engine(ObservabilityConfig(use_mock=True))

        for _ in range(5):
            engine.record_error(
                error_type="TimeoutError",
                component="detector",
                message="Inference timeout on frame",
                camera_id="CAM_01",
                stage="detection",
            )

        errors = engine.get_active_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].count, 5)
        self.assertEqual(errors[0].error_type, "TimeoutError")
        self.assertEqual(errors[0].camera_id, "CAM_01")

    def test_diagnostic_threshold_detection(self):
        """Test diagnostic engine detecting low FPS, high latency, queue depth, and drop rate."""
        obs_engine = create_observability_engine(ObservabilityConfig(
            min_acceptable_fps=20.0,
            max_stage_latency_ms=25.0,
            max_queue_utilization_pct=75.0,
            frame_drop_warning_pct=10.0,
            max_error_count_threshold=3,
        ))

        # Construct abnormal runtime health
        c_health = CameraHealth(
            camera_id="CAM_01",
            state=RuntimeState.RUNNING,
            is_connected=True,
            frames_received=100,
            frames_processed=80,
            frames_dropped=20,
            error_count=4,
            current_fps=12.0,  # Below 20.0 FPS
            stages={
                "detection": StageHealth("detection", StageState.RUNNING, True, avg_latency_ms=35.0),  # Above 25.0ms
            },
        )
        r_health = RuntimeHealth(
            state=RuntimeState.RUNNING,
            total_cameras=1,
            active_cameras=1,
            total_frames_received=100,
            total_frames_processed=80,
            total_frames_dropped=20,
            total_errors=4,
            uptime_seconds=10.0,
            camera_health={"CAM_01": c_health},
        )
        r_metrics = RuntimeMetrics(
            total_cameras=1,
            active_cameras=1,
            total_frames_received=100,
            total_frames_processed=80,
            total_frames_dropped=20,
            drop_rate_pct=20.0,  # Above 10.0%
            total_errors=4,
            avg_pipeline_latency_ms=35.0,
            queue_utilization_pct={"CAM_01": 85.0},  # Above 75.0%
        )

        findings = obs_engine.evaluate_diagnostics(r_health, r_metrics)
        self.assertGreaterEqual(len(findings), 4)

        finding_messages = [f.message for f in findings]
        self.assertTrue(any("below threshold" in m for m in finding_messages))
        self.assertTrue(any("queue utilization is high" in m for m in finding_messages))
        self.assertTrue(any("repeated errors" in m for m in finding_messages))
        self.assertTrue(any("latency on CAM_01" in m for m in finding_messages))

    def test_system_health_aggregation_states(self):
        """Test health aggregator transitions between HEALTHY, DEGRADED, and UNHEALTHY."""
        # 1. Clean state -> HEALTHY
        snap1 = SystemHealthAggregator.aggregate(None, [], [])
        self.assertEqual(snap1.status, SystemHealthStatus.HEALTHY)

        # 2. Warning findings -> DEGRADED
        w_finding = [DiagnosticFinding("f1", DiagnosticSeverity.WARNING, "cam", "Minor issue", 1.0, 2.0)]
        snap2 = SystemHealthAggregator.aggregate(None, w_finding, [])
        self.assertEqual(snap2.status, SystemHealthStatus.DEGRADED)

        # 3. Error findings -> UNHEALTHY
        e_finding = [DiagnosticFinding("f2", DiagnosticSeverity.ERROR, "cam", "Critical issue", 10.0, 2.0)]
        snap3 = SystemHealthAggregator.aggregate(None, e_finding, [])
        self.assertEqual(snap3.status, SystemHealthStatus.UNHEALTHY)

    def test_operational_report_and_json_export(self):
        """Test generating and exporting comprehensive JSON operational reports."""
        obs = create_observability_engine(ObservabilityConfig(use_mock=True))
        obs.record_stage_latency("detection", 15.2, "CAM_01")
        obs.record_stage_latency("tracking", 2.1, "CAM_01")

        r_health = RuntimeHealth(
            state=RuntimeState.RUNNING,
            total_cameras=1,
            active_cameras=1,
            total_frames_received=50,
            total_frames_processed=50,
            total_frames_dropped=0,
            total_errors=0,
            uptime_seconds=5.0,
            camera_health={},
        )
        r_metrics = RuntimeMetrics(
            total_cameras=1,
            active_cameras=1,
            total_frames_received=50,
            total_frames_processed=50,
            total_frames_dropped=0,
            drop_rate_pct=0.0,
            total_errors=0,
            avg_pipeline_latency_ms=17.3,
        )

        report = obs.generate_operational_report(r_health, r_metrics)
        json_str = OperationalReportExporter.to_json(report)

        parsed = json.loads(json_str)
        self.assertIn("report_id", parsed)
        self.assertIn("latency_percentiles", parsed)
        self.assertIn("detection", parsed["latency_percentiles"])
        self.assertEqual(parsed["latency_percentiles"]["detection"]["p50_ms"], 15.2)

    def test_runtime_engine_integration(self):
        """Test attaching observability to RuntimeEngine for event-driven metrics."""
        obs = create_observability_engine(ObservabilityConfig(use_mock=True))
        runtime = create_runtime_engine(PipelineRuntimeConfig(
            use_mock=True,
            cameras=[CameraRuntimeConfig(camera_id="CAM_01")],
        ))

        obs.attach_runtime(runtime)
        runtime.start()

        time.sleep(0.2)
        logs = obs.logger.get_logs(camera_id="CAM_01")
        self.assertGreaterEqual(len(logs), 1)
        self.assertEqual(logs[0].event_type, "camera_started")

        runtime.stop()


if __name__ == "__main__":
    unittest.main()
