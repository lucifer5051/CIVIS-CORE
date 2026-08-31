from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class APIConfig(BaseModel):
    """
    Configuration model for the CIVIS API Gateway.
    """
    host: str = Field(default="0.0.0.0", description="API listen host")
    port: int = Field(default=8000, ge=1, le=65535, description="API listen port")
    enabled: bool = Field(default=True, description="Whether the API gateway is enabled")
    authentication_enabled: bool = Field(default=False, description="Enforce API-key authentication")
    api_key: str = Field(default="civis_secret_key_default", description="Secret API key for HTTP header auth")
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"], description="Allowed CORS origins")
    websocket_enabled: bool = Field(default=True, description="Enable WebSocket live event streaming")
    max_request_size: int = Field(default=10 * 1024 * 1024, description="Max request payload in bytes")
    use_mock: bool = Field(default=False, description="Use in-memory mock engine")


class APIHealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    timestamp: float
    active_cameras: int
    total_cameras: int
    system_load: Optional[Dict[str, Any]] = None


class APICameraStatusResponse(BaseModel):
    camera_id: str
    is_running: bool
    is_paused: bool
    processed_frames: int
    dropped_frames: int
    current_fps: float
    error_count: int


class APICameraActionResponse(BaseModel):
    camera_id: str
    action: str
    success: bool
    message: str


class APIDetectionItem(BaseModel):
    detection_id: str
    camera_id: str
    class_name: str
    class_id: int
    confidence: float
    bbox: List[float]
    timestamp: float


class APITrackItem(BaseModel):
    track_id: int
    camera_id: str
    class_name: str
    confidence: float
    bbox: List[float]
    age: int
    hits: int
    timestamp: float


class APIIdentityItem(BaseModel):
    identity_id: str
    camera_id: str
    track_id: int
    name: str
    confidence: float
    status: str
    timestamp: float


class APIReIDEntityItem(BaseModel):
    global_id: str
    camera_id: str
    track_id: int
    similarity: float
    matched_global_id: Optional[str]
    timestamp: float


class APIBehaviorEventItem(BaseModel):
    behavior_type: str
    camera_id: str
    track_id: int
    confidence: float
    duration_frames: int
    timestamp: float


class APICorrelatedEventItem(BaseModel):
    event_id: str
    event_type: str
    camera_id: str
    confidence: float
    severity: str
    timestamp: float
    summary: str


class APIRiskAssessmentItem(BaseModel):
    assessment_id: str
    camera_id: str
    entity_key: str
    overall_score: float
    severity: str
    confidence: float
    summary: str
    timestamp: float


class APIRiskAlertItem(BaseModel):
    alert_id: str
    assessment_id: str
    camera_id: str
    severity: str
    confidence: float
    explanation: str
    timestamp: float


class APIEvidenceItem(BaseModel):
    evidence_id: str
    camera_id: str
    source_type: str
    sha256_hash: str
    timestamp: float
    verified: bool
    metadata: Dict[str, Any] = Field(default_factory=dict)


class APIEvidenceVerifyResponse(BaseModel):
    evidence_id: str
    is_valid: bool
    computed_hash: str
    stored_hash: str
    message: str


class APIRuntimeStatusResponse(BaseModel):
    state: str
    uptime_seconds: float
    active_cameras: int
    total_cameras: int
    per_camera_status: Dict[str, Dict[str, Any]]


class APIErrorResponse(BaseModel):
    error: str
    detail: str
    status_code: int
    timestamp: float
