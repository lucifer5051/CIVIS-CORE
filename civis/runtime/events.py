from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Callable, Dict, List, Optional


class RuntimeEventType(str, Enum):
    CAMERA_STARTED = "camera_started"
    CAMERA_STOPPED = "camera_stopped"
    CAMERA_ERROR = "camera_error"
    CAMERA_RECONNECTED = "camera_reconnected"
    STAGE_STARTED = "stage_started"
    STAGE_FAILED = "stage_failed"
    STAGE_RECOVERED = "stage_recovered"
    FRAME_DROPPED = "frame_dropped"
    RUNTIME_STARTED = "runtime_started"
    RUNTIME_PAUSED = "runtime_paused"
    RUNTIME_RESUMED = "runtime_resumed"
    RUNTIME_STOPPED = "runtime_stopped"


@dataclass
class RuntimeEvent:
    event_type: RuntimeEventType
    timestamp: float = field(default_factory=time.time)
    camera_id: Optional[str] = None
    stage_name: Optional[str] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class RuntimeEventBus:
    """
    Decoupled operational event bus for dispatching and listening to runtime events.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[RuntimeEventType, List[Callable[[RuntimeEvent], None]]] = {}
        self._global_subscribers: List[Callable[[RuntimeEvent], None]] = []

    def subscribe(
        self,
        event_type: Optional[RuntimeEventType],
        callback: Callable[[RuntimeEvent], None],
    ) -> None:
        """Subscribe to a specific event type or all events (if event_type is None)."""
        if event_type is None:
            self._global_subscribers.append(callback)
        else:
            self._subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event: RuntimeEvent) -> None:
        """Publishes an event to all interested subscribers."""
        # 1. Global listeners
        for cb in self._global_subscribers:
            try:
                cb(event)
            except Exception:
                pass

        # 2. Specific type listeners
        if event.event_type in self._subscribers:
            for cb in self._subscribers[event.event_type]:
                try:
                    cb(event)
                except Exception:
                    pass

    def clear(self) -> None:
        self._subscribers.clear()
        self._global_subscribers.clear()
