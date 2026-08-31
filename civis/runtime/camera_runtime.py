import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from civis.ingestion.models import CameraStatus, FramePacket
from civis.ingestion.stream_manager import StreamManager
from civis.runtime.events import RuntimeEvent, RuntimeEventType, RuntimeEventBus
from civis.runtime.health import HealthMonitor
from civis.runtime.models import (
    CameraHealth,
    CameraRuntimeConfig,
    DropPolicy,
    RuntimeState,
    StageHealth,
    StageState,
)
from civis.runtime.overlay import encode_jpeg, render_pipeline_overlay
from civis.runtime.pipeline import PipelineContext, SequentialPipeline
from civis.runtime.scheduler import BoundedFrameQueue

logger = logging.getLogger(__name__)


class CameraRuntime:
    """
    Dedicated runtime worker executing ingestion, queueing, and sequential pipeline
    processing for a single camera stream. Guarantees fault isolation from other cameras.
    """

    def __init__(
        self,
        config: CameraRuntimeConfig,
        pipeline: SequentialPipeline,
        stream_manager: StreamManager,
        health_monitor: HealthMonitor,
        event_bus: Optional[RuntimeEventBus] = None,
    ) -> None:
        self.config = config
        self.pipeline = pipeline
        self.stream_manager = stream_manager
        self.health_monitor = health_monitor
        self.event_bus = event_bus

        self._state = RuntimeState.CREATED
        self._queue = BoundedFrameQueue(
            maxsize=config.queue_size,
            drop_policy=config.drop_policy,
            on_drop_callback=self._on_frame_dropped,
        )

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused by default

        self._worker_thread: Optional[threading.Thread] = None
        self._ingest_thread: Optional[threading.Thread] = None

        self._frames_received = 0
        self._frames_processed = 0
        self._total_errors = 0
        self._last_processed_time = 0.0
        self._stats_lock = threading.Lock()

        # Live frame buffer for web streaming
        self._latest_frame_jpeg: Optional[bytes] = None
        self._latest_context: Optional[PipelineContext] = None
        self._frame_lock = threading.Lock()
        self._new_frame_event = threading.Event()

        # Optional output callback
        self.on_frame_processed: Optional[Callable[[PipelineContext], None]] = None

    @property
    def camera_id(self) -> str:
        return self.config.camera_id

    @property
    def state(self) -> RuntimeState:
        return self._state

    def _on_frame_dropped(self, packet: FramePacket, reason: str) -> None:
        if self.event_bus:
            self.event_bus.publish(RuntimeEvent(
                event_type=RuntimeEventType.FRAME_DROPPED,
                camera_id=self.camera_id,
                message=reason,
                details={"frame_number": packet.frame_number, "timestamp": packet.timestamp},
            ))

    def start(self) -> None:
        if self._state == RuntimeState.RUNNING:
            return

        self._state = RuntimeState.INITIALIZING
        self._stop_event.clear()
        self._pause_event.set()

        # Start stream if not already started
        if self.stream_manager.get_status(self.camera_id) != CameraStatus.RUNNING:
            self.stream_manager.start_camera(self.camera_id)

        self._state = RuntimeState.RUNNING

        # Worker thread
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name=f"Worker-{self.camera_id}",
            daemon=True,
        )
        self._worker_thread.start()

        # Ingest thread
        self._ingest_thread = threading.Thread(
            target=self._ingest_loop,
            name=f"Ingest-{self.camera_id}",
            daemon=True,
        )
        self._ingest_thread.start()

        if self.event_bus:
            self.event_bus.publish(RuntimeEvent(
                event_type=RuntimeEventType.CAMERA_STARTED,
                camera_id=self.camera_id,
                message="Camera worker started",
            ))

    def _ingest_loop(self) -> None:
        """Reads frames from StreamManager and enqueues into bounded queue."""
        while not self._stop_event.is_set():
            try:
                packet = self.stream_manager.read_frame(self.camera_id, timeout=0.1)
                if packet is None:
                    status = self.stream_manager.get_status(self.camera_id)
                    if status in (CameraStatus.DISCONNECTED, CameraStatus.STOPPED, CameraStatus.ERROR):
                        if not self.config.auto_reconnect or self._stop_event.is_set():
                            break
                        time.sleep(0.1)
                    continue

                with self._stats_lock:
                    self._frames_received += 1
                self._queue.put(packet)

            except Exception as e:
                logger.error(f"Error in ingest loop for {self.camera_id}: {e}")
                with self._stats_lock:
                    self._total_errors += 1
                if self.event_bus:
                    self.event_bus.publish(RuntimeEvent(
                        event_type=RuntimeEventType.CAMERA_ERROR,
                        camera_id=self.camera_id,
                        message=f"Ingestion error: {str(e)}",
                    ))
                time.sleep(0.1)

    def _worker_loop(self) -> None:
        """Consumes frames from bounded queue and processes through pipeline."""
        while not self._stop_event.is_set():
            # Handle pause
            self._pause_event.wait()
            if self._stop_event.is_set():
                break

            packet = self._queue.get(timeout=0.1)
            if packet is None:
                continue

            # Frame skip / interval
            if self.config.frame_interval > 1:
                if packet.frame_number % self.config.frame_interval != 0:
                    continue

            self._process_single_frame(packet)

    def _process_single_frame(self, packet: FramePacket) -> PipelineContext:
        """Executes full pipeline for one frame and records health stats."""
        start_t = time.perf_counter()
        context = PipelineContext(packet=packet, camera_id=self.camera_id)

        try:
            context = self.pipeline.execute(context)
            total_latency_ms = (time.perf_counter() - start_t) * 1000.0
            with self._stats_lock:
                self._frames_processed += 1
                self._last_processed_time = time.time()

            # Record stats
            self.health_monitor.record_frame_processed(self.camera_id, total_latency_ms)
            for stage_name, lat in context.stage_timings_ms.items():
                self.health_monitor.record_stage_execution(self.camera_id, stage_name, lat)

            # Render live overlay and buffer JPEG frame for web streaming
            annotated = render_pipeline_overlay(
                frame=packet.frame,
                context=context,
                camera_id=self.camera_id,
                fps=self.health_monitor.get_camera_fps(self.camera_id),
                latency_ms=total_latency_ms,
                privacy_mode=True,
            )
            jpeg_bytes = encode_jpeg(annotated)
            with self._frame_lock:
                self._latest_frame_jpeg = jpeg_bytes
                self._latest_context = context
            self._new_frame_event.set()

            if self.on_frame_processed:
                self.on_frame_processed(context)

        except Exception as e:
            logger.error(f"Unhandled pipeline failure on camera {self.camera_id}: {e}", exc_info=True)
            with self._stats_lock:
                self._total_errors += 1
            if self.event_bus:
                self.event_bus.publish(RuntimeEvent(
                    event_type=RuntimeEventType.CAMERA_ERROR,
                    camera_id=self.camera_id,
                    message=f"Pipeline execution error: {str(e)}",
                ))

        return context

    def get_latest_frame_jpeg(self, timeout: float = 1.0) -> Optional[bytes]:
        """Waits for next frame or returns current latest annotated frame JPEG."""
        if self._latest_frame_jpeg is not None:
            with self._frame_lock:
                return self._latest_frame_jpeg

        self._new_frame_event.wait(timeout=timeout)
        self._new_frame_event.clear()
        with self._frame_lock:
            return self._latest_frame_jpeg

    def get_latest_context(self) -> Optional[PipelineContext]:
        """Returns latest processed pipeline context containing active detections/tracks/risks."""
        with self._frame_lock:
            return self._latest_context

    def process_frame_sync(self, packet: FramePacket) -> PipelineContext:
        """Synchronous single-frame step for testing and deterministic pipelines."""
        with self._stats_lock:
            self._frames_received += 1
        return self._process_single_frame(packet)

    def pause(self) -> None:
        if self._state == RuntimeState.RUNNING:
            self._pause_event.clear()
            self._state = RuntimeState.PAUSED
            if self.event_bus:
                self.event_bus.publish(RuntimeEvent(
                    event_type=RuntimeEventType.RUNTIME_PAUSED,
                    camera_id=self.camera_id,
                    message="Camera pipeline paused",
                ))

    def resume(self) -> None:
        if self._state == RuntimeState.PAUSED:
            self._pause_event.set()
            self._state = RuntimeState.RUNNING
            if self.event_bus:
                self.event_bus.publish(RuntimeEvent(
                    event_type=RuntimeEventType.RUNTIME_RESUMED,
                    camera_id=self.camera_id,
                    message="Camera pipeline resumed",
                ))

    def stop(self, timeout: float = 3.0) -> None:
        if self._state == RuntimeState.STOPPED:
            return

        self._state = RuntimeState.STOPPING
        self._stop_event.set()
        self._pause_event.set()

        # Wait for threads
        if self._ingest_thread and self._ingest_thread.is_alive():
            self._ingest_thread.join(timeout=timeout)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)

        self.stream_manager.stop_camera(self.camera_id)
        self._queue.clear()
        self._state = RuntimeState.STOPPED

        if self.event_bus:
            self.event_bus.publish(RuntimeEvent(
                event_type=RuntimeEventType.CAMERA_STOPPED,
                camera_id=self.camera_id,
                message="Camera runtime stopped cleanly",
            ))

    def get_health(self) -> CameraHealth:
        stages_health = {stage.name: stage.get_health() for stage in self.pipeline.stages}
        is_conn = self.stream_manager.get_status(self.camera_id) == CameraStatus.RUNNING

        with self._stats_lock:
            recv = self._frames_received
            proc = self._frames_processed
            errs = self._total_errors
            last_ts = self._last_processed_time

        return CameraHealth(
            camera_id=self.camera_id,
            state=self._state,
            is_connected=is_conn,
            frames_received=recv,
            frames_processed=proc,
            frames_dropped=self._queue.dropped_count,
            error_count=errs,
            reconnect_count=0,
            current_fps=self.health_monitor.get_camera_fps(self.camera_id),
            avg_latency_ms=self.health_monitor.get_camera_avg_latency(self.camera_id),
            queue_depth=self._queue.qsize(),
            last_frame_timestamp=last_ts,
            stages=stages_health,
        )
