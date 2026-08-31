import logging
import time
from typing import Callable, Dict, List, Optional

from civis.behavior.factory import create_behavior_engine
from civis.behavior.models import BehaviorConfig
from civis.detection.factory import create_detector
from civis.detection.models import DetectorConfig
from civis.event_intelligence.factory import create_event_intelligence_engine
from civis.event_intelligence.models import EventIntelligenceConfig
from civis.evidence.factory import create_evidence_engine
from civis.evidence.models import EvidenceEngineConfig
from civis.identity.factory import create_identity_engine
from civis.identity.models import IdentityConfig
from civis.ingestion.models import CameraConfig, SourceType
from civis.ingestion.stream_manager import StreamManager
from civis.reid.factory import create_cross_camera_reid_engine
from civis.reid.models import ReIDEngineConfig
from civis.risk.factory import create_risk_engine
from civis.risk.models import RiskEngineConfig
from civis.runtime.base import BasePipelineRuntime
from civis.runtime.camera_runtime import CameraRuntime
from civis.runtime.coordinator import CrossCameraCoordinator
from civis.runtime.events import RuntimeEvent, RuntimeEventBus, RuntimeEventType
from civis.runtime.health import HealthMonitor
from civis.runtime.models import (
    CameraRuntimeConfig,
    PipelineRuntimeConfig,
    RuntimeHealth,
    RuntimeMetrics,
    RuntimeState,
    StageConfig,
)
from civis.runtime.pipeline import (
    BehaviorStage,
    DetectionStage,
    EventIntelligenceStage,
    EvidenceStage,
    IdentityStage,
    ReIDStage,
    RiskAssessmentStage,
    SequentialPipeline,
    TrackingStage,
)
from civis.tracking.factory import create_tracker
from civis.tracking.models import TrackerConfig

logger = logging.getLogger(__name__)


class RuntimeEngine(BasePipelineRuntime):
    """
    Production-grade multi-camera runtime orchestration layer.
    Coordinates concurrent camera ingestion, bounded queues, sequential AI pipeline
    execution, cross-camera intelligence, health tracking, and operational events.
    """

    def __init__(self, config: Optional[PipelineRuntimeConfig] = None) -> None:
        cfg = config if config is not None else PipelineRuntimeConfig()
        super().__init__(cfg)

        self._state = RuntimeState.CREATED
        self._start_time = time.time()

        self.event_bus = RuntimeEventBus()
        self.health_monitor = HealthMonitor()
        self.stream_manager = StreamManager()

        # Shared/coordinator engines
        self.reid_engine = (
            create_cross_camera_reid_engine(ReIDEngineConfig(use_mock=cfg.use_mock))
            if cfg.enable_cross_camera_reid
            else None
        )
        self.coordinator = CrossCameraCoordinator(self.reid_engine)

        self.evidence_engine = (
            create_evidence_engine(EvidenceEngineConfig(use_mock=cfg.use_mock))
            if cfg.enable_evidence_logging
            else None
        )

        self._cameras: Dict[str, CameraRuntime] = {}

        # Initialize configured cameras
        for cam_cfg in cfg.cameras:
            self.add_camera(cam_cfg)

    @property
    def state(self) -> RuntimeState:
        return self._state

    def add_camera(
        self,
        camera_config: CameraRuntimeConfig,
        stream_config: Optional[CameraConfig] = None,
    ) -> CameraRuntime:
        """Adds and initializes a new camera pipeline."""
        cam_id = camera_config.camera_id

        # Register in StreamManager if stream config provided or not present
        if cam_id not in self.stream_manager.list_cameras():
            src_type = camera_config.source_type
            if src_type is None:
                if isinstance(camera_config.source, int) or (isinstance(camera_config.source, str) and camera_config.source.isdigit()):
                    src_type = SourceType.WEBCAM
                elif isinstance(camera_config.source, str) and (camera_config.source.startswith("rtsp://") or camera_config.source.startswith("rtsps://")):
                    src_type = SourceType.RTSP
                else:
                    src_type = SourceType.FILE

            s_cfg = stream_config or CameraConfig(
                camera_id=cam_id,
                name=camera_config.name or cam_id,
                source_type=src_type,
                source=camera_config.source if camera_config.source != "" else "mock_stream.mp4",
                fps_limit=camera_config.target_fps,
                width=camera_config.width,
                height=camera_config.height,
                loop_file=True if src_type == SourceType.FILE else False,
            )
            self.stream_manager.add_camera(s_cfg)

        # Build pipeline stages for this camera
        use_mock = self._config.use_mock
        stages_cfg = self._config.stages

        det_cfg = stages_cfg.get("detection", StageConfig(name="detection", enabled=True))
        trk_cfg = stages_cfg.get("tracking", StageConfig(name="tracking", enabled=True))
        idt_cfg = stages_cfg.get("identity", StageConfig(name="identity", enabled=True))
        rid_cfg = stages_cfg.get("reid", StageConfig(name="reid", enabled=self._config.enable_cross_camera_reid))
        beh_cfg = stages_cfg.get("behavior", StageConfig(name="behavior", enabled=True))
        evt_cfg = stages_cfg.get("event_intelligence", StageConfig(name="event_intelligence", enabled=True))
        rsk_cfg = stages_cfg.get("risk", StageConfig(name="risk", enabled=True))
        evd_cfg = stages_cfg.get("evidence", StageConfig(name="evidence", enabled=self._config.enable_evidence_logging))

        # Instantiate per-camera sub-engines
        detector = create_detector(DetectorConfig(
            use_mock=use_mock,
            model_path="yolo12s.pt",   # small model: far better accuracy than nano, still real-time on RTX 3050
            device="cuda",             # auto-selects cuda:0 if available, else CPU
            conf_threshold=0.25,       # standard confidence threshold
            iou_threshold=0.45,
        ))
        tracker = create_tracker(TrackerConfig(use_mock=use_mock))
        identity_engine = create_identity_engine(IdentityConfig(use_mock=use_mock))
        behavior_engine = create_behavior_engine(BehaviorConfig(use_mock=use_mock))
        event_engine = create_event_intelligence_engine(EventIntelligenceConfig(use_mock=use_mock))
        risk_engine = create_risk_engine(RiskEngineConfig(use_mock=use_mock))

        stages = [
            DetectionStage(detector, enabled=det_cfg.enabled),
            TrackingStage(tracker, enabled=trk_cfg.enabled),
            IdentityStage(identity_engine, enabled=idt_cfg.enabled),
            ReIDStage(self.reid_engine, enabled=rid_cfg.enabled),
            BehaviorStage(behavior_engine, enabled=beh_cfg.enabled),
            EventIntelligenceStage(event_engine, enabled=evt_cfg.enabled),
            RiskAssessmentStage(risk_engine, enabled=rsk_cfg.enabled),
        ]

        if self.evidence_engine and evd_cfg.enabled:
            stages.append(EvidenceStage(self.evidence_engine, enabled=True))

        pipeline = SequentialPipeline(
            stages=stages,
            event_bus=self.event_bus,
            stage_configs=stages_cfg,
        )

        camera_runtime = CameraRuntime(
            config=camera_config,
            pipeline=pipeline,
            stream_manager=self.stream_manager,
            health_monitor=self.health_monitor,
            event_bus=self.event_bus,
        )

        self._cameras[cam_id] = camera_runtime
        return camera_runtime

    def remove_camera(self, camera_id: str) -> None:
        if camera_id in self._cameras:
            self._cameras[camera_id].stop()
            del self._cameras[camera_id]

    def get_camera_runtime(self, camera_id: str) -> Optional[CameraRuntime]:
        return self._cameras.get(camera_id)

    def start(self) -> None:
        if self._state == RuntimeState.RUNNING:
            return

        self._state = RuntimeState.INITIALIZING
        self._start_time = time.time()

        for cam in self._cameras.values():
            cam.start()

        self._state = RuntimeState.RUNNING
        self.event_bus.publish(RuntimeEvent(
            event_type=RuntimeEventType.RUNTIME_STARTED,
            message=f"Runtime started with {len(self._cameras)} cameras",
        ))

    def stop(self) -> None:
        if self._state == RuntimeState.STOPPED:
            return

        self._state = RuntimeState.STOPPING
        timeout = self._config.graceful_shutdown_timeout_sec

        for cam in self._cameras.values():
            cam.stop(timeout=timeout)

        self.stream_manager.stop_all()
        self._state = RuntimeState.STOPPED

        self.event_bus.publish(RuntimeEvent(
            event_type=RuntimeEventType.RUNTIME_STOPPED,
            message="Runtime stopped cleanly",
        ))

    def pause(self) -> None:
        if self._state == RuntimeState.RUNNING:
            for cam in self._cameras.values():
                cam.pause()
            self._state = RuntimeState.PAUSED
            self.event_bus.publish(RuntimeEvent(
                event_type=RuntimeEventType.RUNTIME_PAUSED,
                message="Runtime paused across all cameras",
            ))

    def resume(self) -> None:
        if self._state == RuntimeState.PAUSED:
            for cam in self._cameras.values():
                cam.resume()
            self._state = RuntimeState.RUNNING
            self.event_bus.publish(RuntimeEvent(
                event_type=RuntimeEventType.RUNTIME_RESUMED,
                message="Runtime resumed across all cameras",
            ))

    def get_health(self) -> RuntimeHealth:
        cam_healths = {cid: cr.get_health() for cid, cr in self._cameras.items()}
        active_cams = sum(1 for h in cam_healths.values() if h.state == RuntimeState.RUNNING)
        total_recv = sum(h.frames_received for h in cam_healths.values())
        total_proc = sum(h.frames_processed for h in cam_healths.values())
        total_drop = sum(h.frames_dropped for h in cam_healths.values())
        total_err = sum(h.error_count for h in cam_healths.values())
        uptime = time.time() - self._start_time if self._state == RuntimeState.RUNNING else 0.0

        return RuntimeHealth(
            state=self._state,
            total_cameras=len(self._cameras),
            active_cameras=active_cams,
            total_frames_received=total_recv,
            total_frames_processed=total_proc,
            total_frames_dropped=total_drop,
            total_errors=total_err,
            uptime_seconds=round(uptime, 1),
            camera_health=cam_healths,
        )

    def get_metrics(self) -> RuntimeMetrics:
        health = self.get_health()
        tot_recv = health.total_frames_received
        drop_rate = (health.total_frames_dropped / tot_recv * 100.0) if tot_recv > 0 else 0.0

        fps_map = {cid: h.current_fps for cid, h in health.camera_health.items()}
        q_util_map = {
            cid: round((h.queue_depth / (self._cameras[cid].config.queue_size)) * 100.0, 1)
            for cid, h in health.camera_health.items()
            if cid in self._cameras
        }

        # Average stage latency
        stage_latencies: Dict[str, float] = {}
        stage_counts: Dict[str, int] = {}
        for h in health.camera_health.values():
            for sname, shealth in h.stages.items():
                stage_latencies[sname] = stage_latencies.get(sname, 0.0) + shealth.avg_latency_ms
                stage_counts[sname] = stage_counts.get(sname, 0) + 1

        avg_stage_lat = {
            sname: round(stage_latencies[sname] / stage_counts[sname], 2)
            for sname in stage_latencies
            if stage_counts[sname] > 0
        }

        avg_cam_lat = (
            sum(h.avg_latency_ms for h in health.camera_health.values()) / len(health.camera_health)
            if health.camera_health
            else 0.0
        )

        return RuntimeMetrics(
            total_cameras=health.total_cameras,
            active_cameras=health.active_cameras,
            total_frames_received=health.total_frames_received,
            total_frames_processed=health.total_frames_processed,
            total_frames_dropped=health.total_frames_dropped,
            drop_rate_pct=round(drop_rate, 2),
            total_errors=health.total_errors,
            avg_pipeline_latency_ms=round(avg_cam_lat, 2),
            per_camera_fps=fps_map,
            per_stage_latency_ms=avg_stage_lat,
            queue_utilization_pct=q_util_map,
        )


class MockRuntimeEngine(RuntimeEngine):
    """
    Deterministic Mock Runtime for testing without physical cameras or live models.
    """

    def __init__(self, config: Optional[PipelineRuntimeConfig] = None) -> None:
        cfg = config if config is not None else PipelineRuntimeConfig(use_mock=True)
        cfg.use_mock = True
        super().__init__(cfg)
