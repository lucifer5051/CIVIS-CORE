from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DashboardConfig(BaseModel):
    """
    Configuration for the CIVIS Web Dashboard & Operator Console.
    """
    host: str = Field(default="127.0.0.1", description="Dashboard UI host")
    port: int = Field(default=3000, ge=1, le=65535, description="Dashboard UI port")
    api_base_url: str = Field(default="http://127.0.0.1:8000", description="Backend API base URL")
    ws_url: str = Field(default="ws://127.0.0.1:8000/ws/events", description="WebSocket events URL")
    api_key: Optional[str] = Field(default=None, description="Optional API key for authenticated API endpoints")
    refresh_interval_ms: int = Field(default=2000, ge=500, description="Polling interval for health/status in ms")
    max_timeline_events: int = Field(default=100, ge=10, le=1000, description="Max client-side buffered events")
    theme: str = Field(default="dark", description="UI theme: dark or light")
    enable_controls: bool = Field(default=True, description="Enable runtime and camera control buttons")
