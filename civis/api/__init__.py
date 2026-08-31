"""
External Integration API Gateway Subsystem for CIVIS.
"""

from civis.api.auth import get_auth_dependency
from civis.api.base import BaseAPIEngine
from civis.api.dependencies import APIDependencies
from civis.api.engine import APIEngine, MockAPIEngine
from civis.api.factory import create_api_engine
from civis.api.models import (
    APICameraActionResponse,
    APICameraStatusResponse,
    APIConfig,
    APIDetectionItem,
    APIErrorResponse,
    APIEvidenceItem,
    APIEvidenceVerifyResponse,
    APIHealthResponse,
    APIIdentityItem,
    APIReIDEntityItem,
    APIRiskAlertItem,
    APIRiskAssessmentItem,
    APIRuntimeStatusResponse,
    APITrackItem,
)
from civis.api.websocket import WebSocketConnectionManager

__all__ = [
    "APIConfig",
    "APIHealthResponse",
    "APICameraStatusResponse",
    "APICameraActionResponse",
    "APIDetectionItem",
    "APITrackItem",
    "APIIdentityItem",
    "APIReIDEntityItem",
    "APIRiskAssessmentItem",
    "APIRiskAlertItem",
    "APIEvidenceItem",
    "APIEvidenceVerifyResponse",
    "APIRuntimeStatusResponse",
    "APIErrorResponse",
    "BaseAPIEngine",
    "APIEngine",
    "MockAPIEngine",
    "APIDependencies",
    "WebSocketConnectionManager",
    "create_api_engine",
    "get_auth_dependency",
]
