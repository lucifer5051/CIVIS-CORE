import asyncio
import logging
import time
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from civis.api.auth import get_auth_dependency
from civis.api.base import BaseAPIEngine
from civis.api.dependencies import APIDependencies
from civis.api.models import APIConfig, APIErrorResponse
from civis.api.routes.cameras import create_cameras_router
from civis.api.routes.config import create_config_router
from civis.api.routes.detections import create_detections_router
from civis.api.routes.events import create_events_router
from civis.api.routes.evidence import create_evidence_router
from civis.api.routes.health import create_health_router
from civis.api.routes.identities import create_identities_router
from civis.api.routes.risks import create_risks_router
from civis.api.routes.runtime import create_runtime_router
from civis.api.routes.tracks import create_tracks_router
from civis.api.websocket import WebSocketConnectionManager
from civis.config.engine import MockConfigEngine
from civis.evidence.engine import MockEvidenceEngine
from civis.observability.engine import MockObservabilityEngine
from civis.risk.engine import MockRiskEngine
from civis.runtime.engine import MockRuntimeEngine

logger = logging.getLogger(__name__)


class APIEngine(BaseAPIEngine):
    """
    Production-grade CIVIS-CORE External Integration API Gateway.
    """

    def __init__(
        self,
        config: Optional[APIConfig] = None,
        dependencies: Optional[APIDependencies] = None,
    ) -> None:
        self.config = config or APIConfig()
        self.dependencies = dependencies or APIDependencies()
        self.ws_manager = WebSocketConnectionManager()
        self.app = FastAPI(
            title="CIVIS-CORE External Integration Gateway",
            description="REST & WebSocket API Gateway for CIVIS-CORE Multi-Camera Surveillance & Analytics Pipeline",
            version="1.0.0",
            docs_url="/docs",
            openapi_url="/openapi.json",
        )
        self._setup_cors()
        self._setup_exception_handlers()
        self._setup_routes()
        self._setup_websocket()

    def _setup_cors(self) -> None:
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_exception_handlers(self) -> None:
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": "HTTPException",
                    "detail": exc.detail,
                    "status_code": exc.status_code,
                    "timestamp": time.time(),
                },
            )

        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            logger.error(f"Unhandled API exception on {request.url.path}: {exc}", exc_info=False)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "InternalServerError",
                    "detail": "An internal server error occurred.",
                    "status_code": 500,
                    "timestamp": time.time(),
                },
            )

    def _setup_routes(self) -> None:
        auth_dep = get_auth_dependency(
            auth_enabled=self.config.authentication_enabled,
            expected_key=self.config.api_key,
        )

        routers = [
            create_health_router(self.dependencies, auth_dep),
            create_cameras_router(self.dependencies, auth_dep),
            create_detections_router(self.dependencies, auth_dep),
            create_tracks_router(self.dependencies, auth_dep),
            create_identities_router(self.dependencies, auth_dep),
            create_events_router(self.dependencies, auth_dep),
            create_risks_router(self.dependencies, auth_dep),
            create_evidence_router(self.dependencies, auth_dep),
            create_runtime_router(self.dependencies, auth_dep),
            create_config_router(self.dependencies, auth_dep),
        ]

        for r in routers:
            self.app.include_router(r)
            self.app.include_router(r, prefix="/api")

    def _setup_websocket(self) -> None:
        if not self.config.websocket_enabled:
            return

        async def _handle_ws(websocket: WebSocket):
            await self.ws_manager.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                await self.ws_manager.disconnect(websocket)
            except Exception:
                await self.ws_manager.disconnect(websocket)

        @self.app.websocket("/ws/events")
        async def websocket_events_endpoint(websocket: WebSocket):
            await _handle_ws(websocket)

        @self.app.websocket("/api/ws/events")
        async def websocket_api_events_endpoint(websocket: WebSocket):
            await _handle_ws(websocket)

    def attach_runtime_events(self, runtime: Any) -> None:
        """Subscribes to runtime event bus and camera processing to forward live telemetry to WebSockets."""
        if hasattr(runtime, "event_bus") and runtime.event_bus is not None:
            def _forward_event(evt):
                msg = {
                    "event_type": evt.event_type.value if hasattr(evt.event_type, "value") else str(evt.event_type),
                    "camera_id": evt.camera_id,
                    "timestamp": evt.timestamp,
                    "stage_name": getattr(evt, "stage_name", None),
                    "message": getattr(evt, "message", ""),
                    "data": getattr(evt, "details", {}) or getattr(evt, "data", {}),
                }
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self.ws_manager.broadcast(msg))
                except Exception:
                    pass

            runtime.event_bus.subscribe(None, _forward_event)

        # Attach frame telemetry callback to camera runtimes
        if hasattr(runtime, "_cameras"):
            for cam_id, cam_rt in runtime._cameras.items():
                def _make_telemetry_callback(cid):
                    def _on_processed(ctx):
                        telemetry = {
                            "event_type": "pipeline_telemetry",
                            "camera_id": cid,
                            "timestamp": ctx.packet.timestamp if ctx.packet else time.time(),
                            "frame_number": ctx.packet.frame_number if ctx.packet else 0,
                            "data": {
                                "stage_timings_ms": ctx.stage_timings_ms,
                                "detections_count": len(ctx.detection_result.detections) if ctx.detection_result else 0,
                                "tracks_count": len(ctx.track_result.tracks) if ctx.track_result else 0,
                                "tracks": [
                                    {
                                        "track_id": t.track_id,
                                        "class_name": t.class_name,
                                        "confidence": round(t.confidence, 3),
                                        "state": t.state.value if hasattr(t.state, "value") else str(t.state),
                                    }
                                    for t in (ctx.track_result.tracks if ctx.track_result else [])
                                ],
                                "identities": [
                                    {
                                        "track_id": i.track_id,
                                        "identity_id": i.identity_id,
                                        "name": i.name,
                                        "state": i.state.value if hasattr(i.state, "value") else str(i.state),
                                        "confidence": i.recognition_confidence,
                                    }
                                    for i in (ctx.identity_result.identities if ctx.identity_result else [])
                                ],
                                "global_entities": [
                                    {
                                        "global_entity_id": e.global_entity_id,
                                        "num_cameras": e.num_associated_cameras,
                                        "primary_identity": e.primary_identity_id,
                                    }
                                    for e in (ctx.reid_result.global_entities if ctx.reid_result else [])
                                ],
                                "behavior_events": [
                                    {
                                        "event_type": b.event_type,
                                        "track_id": b.primary_track_id,
                                        "zone_id": b.zone_id,
                                    }
                                    for b in (ctx.behavior_result.events if ctx.behavior_result else [])
                                ],
                                "risk_score": max([a.severity_score for a in ctx.risk_result.assessments], default=0.0) if ctx.risk_result and ctx.risk_result.assessments else 0.0,
                                "risk_alerts": [
                                    {
                                        "alert_id": alt.alert_id,
                                        "severity": alt.severity.value if hasattr(alt.severity, "value") else str(alt.severity),
                                        "headline": alt.headline,
                                    }
                                    for alt in (ctx.risk_result.alerts if ctx.risk_result else [])
                                ],
                            },
                        }
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.create_task(self.ws_manager.broadcast(telemetry))
                        except Exception:
                            pass
                    return _on_processed

                cam_rt.on_frame_processed = _make_telemetry_callback(cam_id)

    def get_app(self) -> FastAPI:
        return self.app

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class MockAPIEngine(APIEngine):
    """
    Mock API Engine pre-populated with deterministic in-memory mock data for tests and demos.
    """

    def __init__(self, config: Optional[APIConfig] = None) -> None:
        mock_cfg = config or APIConfig(use_mock=True, authentication_enabled=False)
        from civis.runtime.models import CameraRuntimeConfig, PipelineRuntimeConfig
        mock_rt = MockRuntimeEngine(PipelineRuntimeConfig(
            use_mock=True,
            cameras=[CameraRuntimeConfig(camera_id="CAM_01", source="0", use_mock=True)],
        ))
        mock_obs = MockObservabilityEngine()
        mock_cfg_eng = MockConfigEngine()
        mock_ev = MockEvidenceEngine()
        mock_rsk = MockRiskEngine()

        deps = APIDependencies(
            runtime_engine=mock_rt,
            observability_engine=mock_obs,
            config_engine=mock_cfg_eng,
            evidence_engine=mock_ev,
            risk_engine=mock_rsk,
        )

        # Pre-seed analytics mock records
        now = time.time()
        deps.in_memory_analytics["detections"] = [
            {"detection_id": "det_001", "camera_id": "CAM_01", "class_name": "person", "class_id": 0, "confidence": 0.92, "bbox": [100.0, 150.0, 200.0, 400.0], "timestamp": now},
            {"detection_id": "det_002", "camera_id": "CAM_02", "class_name": "backpack", "class_id": 24, "confidence": 0.85, "bbox": [50.0, 80.0, 120.0, 160.0], "timestamp": now},
        ]
        deps.in_memory_analytics["tracks"] = [
            {"track_id": 1, "camera_id": "CAM_01", "class_name": "person", "confidence": 0.92, "bbox": [100.0, 150.0, 200.0, 400.0], "age": 45, "hits": 45, "timestamp": now},
        ]
        deps.in_memory_analytics["identities"] = [
            {"identity_id": "usr_alpha_101", "camera_id": "CAM_01", "track_id": 1, "name": "Jane Doe", "confidence": 0.96, "status": "verified", "timestamp": now},
        ]
        deps.in_memory_analytics["reid_entities"] = [
            {"global_id": "gid_881", "camera_id": "CAM_01", "track_id": 1, "similarity": 0.88, "matched_global_id": "gid_881", "timestamp": now},
        ]
        deps.in_memory_analytics["behavior_events"] = [
            {"behavior_type": "loitering", "camera_id": "CAM_01", "track_id": 1, "confidence": 0.89, "duration_frames": 120, "timestamp": now},
        ]
        deps.in_memory_analytics["events"] = [
            {"event_id": "evt_7701", "event_type": "restricted_area_loitering", "camera_id": "CAM_01", "confidence": 0.91, "severity": "high", "timestamp": now, "summary": "Unattended loitering in restricted zone"},
        ]
        deps.in_memory_analytics["risks"] = [
            {"assessment_id": "rsk_9901", "camera_id": "CAM_01", "entity_key": "CAM_01_tr_1", "overall_score": 0.78, "severity": "high", "confidence": 0.88, "summary": "High risk intrusion", "timestamp": now},
        ]
        deps.in_memory_analytics["alerts"] = [
            {"alert_id": "alt_1102", "assessment_id": "rsk_9901", "camera_id": "CAM_01", "severity": "high", "confidence": 0.88, "explanation": "Intrusion score exceeded threshold", "timestamp": now},
        ]

        super().__init__(config=mock_cfg, dependencies=deps)
