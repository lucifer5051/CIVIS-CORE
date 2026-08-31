import threading
from collections import deque
from typing import Any, Callable, Optional, Tuple

from civis.ingestion.models import FramePacket
from civis.runtime.models import DropPolicy


class BoundedFrameQueue:
    """
    Thread-safe bounded frame queue implementing real-time video analytics backpressure
    and load-shedding policies (Drop Oldest / Drop Newest / Block).
    """

    def __init__(
        self,
        maxsize: int = 10,
        drop_policy: DropPolicy = DropPolicy.DROP_OLDEST,
        on_drop_callback: Optional[Callable[[FramePacket, str], None]] = None,
    ) -> None:
        self.maxsize = max(1, maxsize)
        self.drop_policy = drop_policy
        self.on_drop_callback = on_drop_callback

        self._queue: deque = deque()
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)

        self._received_count: int = 0
        self._processed_count: int = 0
        self._dropped_count: int = 0

    @property
    def received_count(self) -> int:
        return self._received_count

    @property
    def processed_count(self) -> int:
        return self._processed_count

    @property
    def dropped_count(self) -> int:
        return self._dropped_count

    def qsize(self) -> int:
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._queue) == 0

    def is_full(self) -> bool:
        with self._lock:
            return len(self._queue) >= self.maxsize

    def utilization_pct(self) -> float:
        with self._lock:
            return round((len(self._queue) / self.maxsize) * 100.0, 1)

    def put(self, packet: FramePacket, timeout: Optional[float] = None) -> bool:
        """
        Puts a frame into the bounded queue according to the configured drop policy.
        Returns True if accepted/queued, False if dropped.
        """
        with self._lock:
            self._received_count += 1

            if len(self._queue) >= self.maxsize:
                if self.drop_policy == DropPolicy.DROP_OLDEST:
                    # Drop oldest item from front of queue
                    old_packet = self._queue.popleft()
                    self._dropped_count += 1
                    if self.on_drop_callback:
                        self.on_drop_callback(old_packet, "Queue full: dropped oldest frame for real-time latency")
                    self._queue.append(packet)
                    self._not_empty.notify()
                    return True

                elif self.drop_policy == DropPolicy.DROP_NEWEST:
                    # Drop this new incoming packet
                    self._dropped_count += 1
                    if self.on_drop_callback:
                        self.on_drop_callback(packet, "Queue full: dropped arriving frame")
                    return False

                elif self.drop_policy == DropPolicy.BLOCK:
                    # Block until space is available
                    end_time = None
                    if timeout is not None:
                        import time
                        end_time = time.time() + timeout

                    while len(self._queue) >= self.maxsize:
                        remaining = None
                        if end_time is not None:
                            import time
                            remaining = end_time - time.time()
                            if remaining <= 0:
                                self._dropped_count += 1
                                return False
                        self._not_full.wait(timeout=remaining)

                    self._queue.append(packet)
                    self._not_empty.notify()
                    return True

            # Normal enqueue when not full
            self._queue.append(packet)
            self._not_empty.notify()
            return True

    def get(self, timeout: Optional[float] = None) -> Optional[FramePacket]:
        """
        Retrieves next frame from the queue. Blocks up to timeout seconds.
        """
        with self._lock:
            end_time = None
            if timeout is not None:
                import time
                end_time = time.time() + timeout

            while len(self._queue) == 0:
                remaining = None
                if end_time is not None:
                    import time
                    remaining = end_time - time.time()
                    if remaining <= 0:
                        return None
                self._not_empty.wait(timeout=remaining)

            packet = self._queue.popleft()
            self._processed_count += 1
            self._not_full.notify()
            return packet

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()
            self._not_full.notify_all()
