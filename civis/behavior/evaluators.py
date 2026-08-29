import math, time
from typing import Dict, List, Optional, Set, Tuple

from civis.behavior.models import BehaviorConfig, BehaviorEvent, Point2D
from civis.tracking.models import TrackedObject


class EventCooldownManager:
    """
    Event deduplication and cooldown manager to prevent repeated identical events every frame.
    """

    def __init__(self, default_cooldown_sec: float = 5.0) -> None:
        self.default_cooldown_sec = default_cooldown_sec
        self.last_event_times: Dict[str, float] = {}

    def should_emit(self, event_key: str, current_time: float, cooldown_sec: Optional[float] = None) -> bool:
        cooldown = cooldown_sec if cooldown_sec is not None else self.default_cooldown_sec
        last_time = self.last_event_times.get(event_key, 0.0)
        if current_time - last_time >= cooldown:
            self.last_event_times[event_key] = current_time
            return True
        return False

    def reset(self) -> None:
        self.last_event_times.clear()


class ProximityEvaluator:
    """
    Evaluates geometric closeness between active tracks.
    Represents geometric spatial proximity only (does not claim interaction).
    Configurable by object class filter.
    """

    @staticmethod
    def evaluate_proximity(
        tracks: List[TrackedObject],
        threshold_pixels: float,
        class_filter: Optional[List[str]] = None,
    ) -> Tuple[Dict[int, List[int]], List[Tuple[int, int, float]]]:
        proximity_map: Dict[int, List[int]] = {t.track_id: [] for t in tracks}
        pairs: List[Tuple[int, int, float]] = []

        n = len(tracks)
        for i in range(n):
            t1 = tracks[i]
            if class_filter is not None and t1.class_name not in class_filter:
                continue

            cx1, cy1 = (t1.bbox.x1 + t1.bbox.width / 2.0, t1.bbox.y2)

            for j in range(i + 1, n):
                t2 = tracks[j]
                if class_filter is not None and t2.class_name not in class_filter:
                    continue

                cx2, cy2 = (t2.bbox.x1 + t2.bbox.width / 2.0, t2.bbox.y2)
                dist = math.sqrt((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2)

                if dist <= threshold_pixels:
                    proximity_map[t1.track_id].append(t2.track_id)
                    proximity_map[t2.track_id].append(t1.track_id)
                    pairs.append((t1.track_id, t2.track_id, round(dist, 2)))

        return proximity_map, pairs
