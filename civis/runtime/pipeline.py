from dataclasses import dataclass, field
import logging
import time
from typing import Any, Dict, List, Optional

from civis.behavior.base import BaseBehaviorEngine
from civis.behavior.models import BehaviorResult
from civis.detection.base import BaseDetector
from civis.detection.models import DetectionResult
from civis.event_intelligence.base import BaseEventIntelligenceEngine
from civis.event_intelligence.models import EventIntelligenceResult
from civis.evidence.base import BaseEvidenceEngine
from civis.evidence.models import EvidenceRecord
from civis.identity.engine import IdentityEngine
from civis.identity.models import IdentityResult
from civis.ingestion.models import FramePacket
from civis.reid.base import BaseCrossCameraEngine
from civis.reid.models import CrossCameraReIDResult
from civis.risk.base import BaseRiskEngine
from civis.risk.models import RiskAssessmentResult
from civis.runtime.base import BasePipelineStage
from civis.runtime.events import RuntimeEvent, RuntimeEventBus, RuntimeEventType
from civis.runtime.models import StageConfig
from civis.tracking.base import BaseTracker
from civis.tracking.models import TrackResult

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """
    Context carrier passing state down the CIVIS sequential pipeline.
    """
    packet: FramePacket
    camera_id: str
    detection_result: Optional[DetectionResult] = None
    track_result: Optional[TrackResult] = None
    identity_result: Optional[IdentityResult] = None
    reid_result: Optional[CrossCameraReIDResult] = None
    behavior_result: Optional[BehaviorResult] = None
    event_result: Optional[EventIntelligenceResult] = None
    risk_result: Optional[RiskAssessmentResult] = None
    evidence_records: List[EvidenceRecord] = field(default_factory=list)
    stage_timings_ms: Dict[str, float] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DetectionStage(BasePipelineStage):
    def __init__(self, detector: BaseDetector, enabled: bool = True) -> None:
        super().__init__("detection", enabled=enabled)
        self.detector = detector

    def process(self, context: PipelineContext) -> PipelineContext:
        if not self._enabled:
            return context
        context.detection_result = self.detector.detect(context.packet)
        return context


class TrackingStage(BasePipelineStage):
    def __init__(self, tracker: BaseTracker, enabled: bool = True) -> None:
        super().__init__("tracking", enabled=enabled)
        self.tracker = tracker

    def process(self, context: PipelineContext) -> PipelineContext:
        if not self._enabled:
            return context
        if context.detection_result is None:
            return context
        context.track_result = self.tracker.update(context.detection_result)
        return context


class IdentityStage(BasePipelineStage):
    def __init__(self, identity_engine: IdentityEngine, enabled: bool = True) -> None:
        super().__init__("identity", enabled=enabled)
        self.identity_engine = identity_engine

    def process(self, context: PipelineContext) -> PipelineContext:
        if not self._enabled:
            return context
        if context.track_result is None:
            return context
        context.identity_result = self.identity_engine.process(context.packet, context.track_result)
        return context


class ReIDStage(BasePipelineStage):
    def __init__(self, reid_engine: Optional[BaseCrossCameraEngine] = None, enabled: bool = True) -> None:
        super().__init__("reid", enabled=enabled)
        self.reid_engine = reid_engine

    def process(self, context: PipelineContext) -> PipelineContext:
        if not self._enabled or self.reid_engine is None:
            return context
        if context.track_result is None:
            return context

        # Process single camera frame through cross-camera engine
        packets = {context.camera_id: context.packet}
        tracks = {context.camera_id: context.track_result}
        identities = {context.camera_id: context.identity_result} if context.identity_result else None

        context.reid_result = self.reid_engine.process(packets, tracks, identities)
        return context


class BehaviorStage(BasePipelineStage):
    def __init__(self, behavior_engine: BaseBehaviorEngine, enabled: bool = True) -> None:
        super().__init__("behavior", enabled=enabled)
        self.behavior_engine = behavior_engine

    def process(self, context: PipelineContext) -> PipelineContext:
        if not self._enabled:
            return context
        if context.track_result is None:
            return context
        context.behavior_result = self.behavior_engine.process(context.track_result, context.identity_result)
        return context


class EventIntelligenceStage(BasePipelineStage):
    def __init__(self, event_engine: BaseEventIntelligenceEngine, enabled: bool = True) -> None:
        super().__init__("event_intelligence", enabled=enabled)
        self.event_engine = event_engine

    def process(self, context: PipelineContext) -> PipelineContext:
        if not self._enabled:
            return context
        if context.behavior_result is None:
            return context
        context.event_result = self.event_engine.process(
            context.behavior_result,
            context.identity_result,
            context.track_result,
        )
        return context


class RiskAssessmentStage(BasePipelineStage):
    def __init__(self, risk_engine: BaseRiskEngine, enabled: bool = True) -> None:
        super().__init__("risk", enabled=enabled)
        self.risk_engine = risk_engine

    def process(self, context: PipelineContext) -> PipelineContext:
        if not self._enabled:
            return context
        if context.event_result is None:
            return context
        context.risk_result = self.risk_engine.assess(
            context.event_result,
            context.behavior_result,
            context.identity_result,
            context.track_result,
        )
        return context


class EvidenceStage(BasePipelineStage):
    def __init__(self, evidence_engine: BaseEvidenceEngine, enabled: bool = True) -> None:
        super().__init__("evidence", enabled=enabled)
        self.evidence_engine = evidence_engine

    def process(self, context: PipelineContext) -> PipelineContext:
        if not self._enabled:
            return context
        records = self.evidence_engine.ingest_pipeline_frame(
            detection_result=context.detection_result,
            track_result=context.track_result,
            identity_result=context.identity_result,
            reid_result=context.reid_result,
            behavior_result=context.behavior_result,
            event_result=context.event_result,
            risk_result=context.risk_result,
        )
        context.evidence_records.extend(records)
        return context


class SequentialPipeline:
    """
    Executes a configured sequence of BasePipelineStage objects with
    per-stage latency timing, error isolation boundaries, and event notifications.
    """

    def __init__(
        self,
        stages: List[BasePipelineStage],
        event_bus: Optional[RuntimeEventBus] = None,
        stage_configs: Optional[Dict[str, StageConfig]] = None,
    ) -> None:
        self.stages = stages
        self.event_bus = event_bus
        self.stage_configs = stage_configs or {}

    def execute(self, context: PipelineContext) -> PipelineContext:
        for stage in self.stages:
            if not stage.enabled:
                continue

            cfg = self.stage_configs.get(stage.name)
            max_retries = cfg.max_retries if cfg else 0

            success = False
            attempts = 0
            start_t = time.perf_counter()

            while attempts <= max_retries and not success:
                attempts += 1
                try:
                    context = stage.process(context)
                    elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                    stage.record_success(elapsed_ms, time.time())
                    context.stage_timings_ms[stage.name] = round(elapsed_ms, 2)
                    success = True

                except Exception as e:
                    err_msg = f"Stage '{stage.name}' failed on attempt {attempts}: {str(e)}"
                    logger.error(err_msg, exc_info=True)
                    if attempts > max_retries:
                        stage.record_failure(str(e))
                        context.errors[stage.name] = str(e)
                        if self.event_bus:
                            self.event_bus.publish(RuntimeEvent(
                                event_type=RuntimeEventType.STAGE_FAILED,
                                camera_id=context.camera_id,
                                stage_name=stage.name,
                                message=str(e),
                            ))

        return context
