import math, time
from typing import Dict, List, Optional, Tuple
from civis.behavior.models import Point2D


class TrackTrajectory:
    def __init__(self, camera_id: str, track_id: int, max_seconds: float = 30.0) -> None:
        self.camera_id = camera_id
        self.track_id = track_id
        self.max_seconds = max_seconds
        self.positions: List[Point2D] = []
        self.timestamps: List[float] = []
        self.dwell_start_time: Optional[float] = None
        self.last_stationary_pos: Optional[Point2D] = None

    def add_point(self, point: Point2D, timestamp: float) -> None:
        self.positions.append(point)
        self.timestamps.append(timestamp)

        # Trim old history
        cutoff = timestamp - self.max_seconds
        while len(self.timestamps) > 1 and self.timestamps[0] < cutoff:
            self.timestamps.pop(0)
            self.positions.pop(0)

    @property
    def current_position(self) -> Optional[Point2D]:
        return self.positions[-1] if self.positions else None

    @property
    def previous_position(self) -> Optional[Point2D]:
        return self.positions[-2] if len(self.positions) >= 2 else self.current_position

    def calculate_velocity(self) -> Tuple[float, float, float]:
        """Calculates (vx, vy, speed) in pixels/sec over recent history."""
        if len(self.positions) < 2:
            return (0.0, 0.0, 0.0)

        p_curr = self.positions[-1]
        p_prev = self.positions[-2]
        t_curr = self.timestamps[-1]
        t_prev = self.timestamps[-2]

        dt = t_curr - t_prev
        if dt <= 0:
            return (0.0, 0.0, 0.0)

        vx = (p_curr.x - p_prev.x) / dt
        vy = (p_curr.y - p_prev.y) / dt
        speed = math.sqrt(vx * vx + vy * vy)
        return (vx, vy, speed)

    def calculate_dwell_time(self, current_time: float, stationary_radius_px: float = 20.0) -> float:
        """Calculates dwelling time in seconds if object remains stationary."""
        curr = self.current_position
        if curr is None:
            return 0.0

        if self.last_stationary_pos is None:
            self.last_stationary_pos = curr
            self.dwell_start_time = current_time
            return 0.0

        dist = math.sqrt((curr.x - self.last_stationary_pos.x) ** 2 + (curr.y - self.last_stationary_pos.y) ** 2)

        if dist <= stationary_radius_px:
            if self.dwell_start_time is None:
                self.dwell_start_time = current_time
            return max(0.0, current_time - self.dwell_start_time)
        else:
            # Motion occurred, reset dwell center
            self.last_stationary_pos = curr
            self.dwell_start_time = current_time
            return 0.0


class TrajectoryMemory:
    def __init__(self, max_seconds: float = 30.0) -> None:
        self.max_seconds = max_seconds
        self.trajectories: Dict[Tuple[str, int], TrackTrajectory] = {}

    def get_trajectory(self, camera_id: str, track_id: int) -> TrackTrajectory:
        key = (camera_id, track_id)
        if key not in self.trajectories:
            self.trajectories[key] = TrackTrajectory(camera_id, track_id, self.max_seconds)
        return self.trajectories[key]

    def reset(self, camera_id: Optional[str] = None) -> None:
        if camera_id is None:
            self.trajectories.clear()
        else:
            keys_to_del = [k for k in self.trajectories.keys() if k[0] == camera_id]
            for k in keys_to_del:
                del self.trajectories[k]
