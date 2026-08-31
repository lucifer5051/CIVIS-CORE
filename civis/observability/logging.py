from collections import deque
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from civis.observability.models import LogLevel, LogRecord

logger = logging.getLogger("civis.observability")


class StructuredLogger:
    """
    Thread-safe structured logging engine with rolling in-memory buffer and JSON formatting.
    """

    def __init__(self, max_buffer_size: int = 1000) -> None:
        self._buffer: deque = deque(maxlen=max_buffer_size)
        self._lock = threading.Lock()

    def log(
        self,
        level: LogLevel,
        component: str,
        message: str,
        camera_id: Optional[str] = None,
        stage: Optional[str] = None,
        event_type: Optional[str] = None,
        error_details: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LogRecord:
        rec = LogRecord(
            timestamp=time.time(),
            level=level,
            component=component,
            message=message,
            camera_id=camera_id,
            stage=stage,
            event_type=event_type,
            error_details=error_details,
            metadata=metadata or {},
        )

        with self._lock:
            self._buffer.append(rec)

        # Mirror to Python standard logger
        py_level = getattr(logging, level.value, logging.INFO)
        cam_ctx = f"[{camera_id}]" if camera_id else ""
        stage_ctx = f"[{stage}]" if stage else ""
        logger.log(py_level, "%s%s %s: %s", cam_ctx, stage_ctx, component, message)

        return rec

    def debug(self, component: str, message: str, **kwargs: Any) -> LogRecord:
        return self.log(LogLevel.DEBUG, component, message, **kwargs)

    def info(self, component: str, message: str, **kwargs: Any) -> LogRecord:
        return self.log(LogLevel.INFO, component, message, **kwargs)

    def warning(self, component: str, message: str, **kwargs: Any) -> LogRecord:
        return self.log(LogLevel.WARNING, component, message, **kwargs)

    def error(self, component: str, message: str, **kwargs: Any) -> LogRecord:
        return self.log(LogLevel.ERROR, component, message, **kwargs)

    def critical(self, component: str, message: str, **kwargs: Any) -> LogRecord:
        return self.log(LogLevel.CRITICAL, component, message, **kwargs)

    def get_logs(
        self,
        limit: int = 100,
        min_level: Optional[LogLevel] = None,
        camera_id: Optional[str] = None,
    ) -> List[LogRecord]:
        level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4,
        }
        min_rank = level_order.get(min_level, 0) if min_level else 0

        with self._lock:
            records = list(self._buffer)

        filtered = [
            r for r in records
            if level_order.get(r.level, 0) >= min_rank
            and (camera_id is None or r.camera_id == camera_id)
        ]
        return filtered[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
