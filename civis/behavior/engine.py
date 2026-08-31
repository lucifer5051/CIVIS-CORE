import logging
import time
from typing import Dict, List, Optional

from civis.behavior.base import BaseBehaviorEngine
from civis.behavior.evaluators import EventCooldownManager, ProximityEvaluator
from civis.behavior.models import (
    BehaviorConfig,
    BehaviorEvent,
    BehaviorObservation,
    BehaviorResult,
    BehaviorState,
    Point2D,
)
from civis.behavior.trajectory import TrajectoryMemory
from civis.behavior.zones import ZoneEvaluator
from civis.identity.models import IdentityResult
from civis.tracking.models import TrackResult

logger = logging.getLogger(__name__)


class BehaviorEngine(BaseBehaviorEngine):
    """
    Behavior Analysis Engine for CIVIS.
    Consumes TrackResult and optional IdentityResult payloads to analyze motion,
    dwell periods, zone crossings, geometric proximity, and crowd density.
    """

    def __init__(self, config: Optional[BehaviorConfig] = None) -> None:
        cfg = config if config is not None else BehaviorConfig()
        super().__init__(cfg)
        self._trajectory_memory = TrajectoryMemory(max_seconds=cfg.max_trajectory_seconds)
        self._zone_evaluator = ZoneEvaluator(zones=cfg.zones, tripwires=cfg.tripwires)
        self._cooldown_manager = EventCooldownManager(default_cooldown_sec=cfg.event_cooldown_seconds)

    def reset(self, camera_id: Optional[str] = None) -> None:
        self._trajectory_memory.reset(camera_id)
        if camera_id is None:
            self._cooldown_manager.reset()

    def process(
        self,
        track_result: TrackResult,
        identity_result: Optional[IdentityResult] = None,
    ) -> BehaviorResult:
        start_time = time.perf_counter()
        cam_id = track_result.camera_id
        current_time = track_result.timestamp

        # Identity lookup map (track_id -> identity_id)
        identity_map: Dict[int, str] = {}
        if identity_result is not None:
            for assoc in identity_result.identities:
                identity_map[assoc.track_id] = assoc.identity_id

        active_tracks = [t for t in track_result.tracks if t.state.value in ("new", "tracked")]

        # 1. Evaluate pairwise geometric proximity
        proximity_map, proximity_pairs = ProximityEvaluator.evaluate_proximity(
            tracks=active_tracks,
            threshold_pixels=self._config.proximity_threshold_pixels,
            class_filter=self._config.proximity_class_filter,
        )

        observations: List[BehaviorObservation] = []
        events: List[BehaviorEvent] = []
        zone_counts: Dict[str, int] = {z.zone_id: 0 for z in self._config.zones}

        event_counter = 0

        # 2. Process each track trajectory
        for track in active_tracks:
            foot_x = track.bbox.x1 + track.bbox.width / 2.0
            foot_y = track.bbox.y2
            curr_pos = Point2D(x=foot_x, y=foot_y)

            trajectory = self._trajectory_memory.get_trajectory(cam_id, track.track_id)
            prev_pos = trajectory.current_position

            trajectory.add_point(curr_pos, current_time)

            vx, vy, speed = trajectory.calculate_velocity()
            dwell_time = trajectory.calculate_dwell_time(
                current_time=current_time,
                stationary_radius_px=20.0,
            )

            # Zone containment check
            current_zones = self._zone_evaluator.get_containing_zones(curr_pos)
            for zid in current_zones:
                zone_counts[zid] = zone_counts.get(zid, 0) + 1

            identity_id = identity_map.get(track.track_id, "UNKNOWN")

            # Determine BehaviorState
            if dwell_time >= self._config.dwell_threshold_seconds:
                state = BehaviorState.LOITERING
            elif speed <= self._config.stationary_speed_threshold_px_sec:
                state = BehaviorState.DWELLING if dwell_time > 2.0 else BehaviorState.STATIONARY
            else:
                state = BehaviorState.MOVING

            prox_ids = proximity_map.get(track.track_id, [])

            obs = BehaviorObservation(
                track_id=track.track_id,
                camera_id=cam_id,
                identity_id=identity_id,
                state=state,
                speed_px_sec=round(speed, 2),
                dwell_time_sec=round(dwell_time, 2),
                current_zones=current_zones,
                proximity_track_ids=prox_ids,
                metadata={
                    "vx": round(vx, 2),
                    "vy": round(vy, 2),
                    "class_name": track.class_name,
                },
            )
            observations.append(obs)

            # --- Event Triggering & Cooldown Deduplication ---

            # Event 1: Loitering Detected
            if state == BehaviorState.LOITERING:
                key = f"{cam_id}_loiter_{track.track_id}"
                if self._cooldown_manager.should_emit(key, current_time):
                    event_counter += 1
                    events.append(
                        BehaviorEvent(
                            event_id=f"evt_{cam_id}_{track.track_id}_{event_counter}",
                            camera_id=cam_id,
                            frame_id=track_result.frame_id,
                            timestamp=current_time,
                            event_type="LOITERING_DETECTED",
                            primary_track_id=track.track_id,
                            identity_id=identity_id,
                            zone_id=current_zones[0] if current_zones else None,
                            metadata={"dwell_time_sec": round(dwell_time, 1)},
                        )
                    )

            # Event 2: Tripwire Crossing
            if prev_pos is not None:
                crossed_lines = self._zone_evaluator.check_tripwire_crossing(prev_pos, curr_pos)
                for tripwire in crossed_lines:
                    key = f"{cam_id}_tripwire_{tripwire.tripwire_id}_{track.track_id}"
                    if self._cooldown_manager.should_emit(key, current_time, cooldown_sec=1.0):
                        event_counter += 1
                        events.append(
                            BehaviorEvent(
                                event_id=f"evt_{cam_id}_{track.track_id}_{event_counter}",
                                camera_id=cam_id,
                                frame_id=track_result.frame_id,
                                timestamp=current_time,
                                event_type="TRIPWIRE_CROSSING",
                                primary_track_id=track.track_id,
                                identity_id=identity_id,
                                zone_id=tripwire.tripwire_id,
                                metadata={"tripwire_name": tripwire.name},
                            )
                        )

        # Event 3: Geometric Proximity Near Event
        for tid1, tid2, dist in proximity_pairs:
            key = f"{cam_id}_proximity_{min(tid1, tid2)}_{max(tid1, tid2)}"
            if self._cooldown_manager.should_emit(key, current_time):
                event_counter += 1
                events.append(
                    BehaviorEvent(
                        event_id=f"evt_{cam_id}_prox_{event_counter}",
                        camera_id=cam_id,
                        frame_id=track_result.frame_id,
                        timestamp=current_time,
                        event_type="PROXIMITY_NEAR",
                        primary_track_id=tid1,
                        secondary_track_ids=[tid2],
                        metadata={"distance_pixels": dist},
                    )
                )

        # Event 4: Crowd Density High Event
        for zid, count in zone_counts.items():
            if count >= self._config.crowd_density_threshold:
                key = f"{cam_id}_density_{zid}"
                if self._cooldown_manager.should_emit(key, current_time):
                    event_counter += 1
                    events.append(
                        BehaviorEvent(
                            event_id=f"evt_{cam_id}_density_{event_counter}",
                            camera_id=cam_id,
                            frame_id=track_result.frame_id,
                            timestamp=current_time,
                            event_type="CROWD_DENSITY_HIGH",
                            primary_track_id=0,
                            zone_id=zid,
                            metadata={"active_count": count, "threshold": self._config.crowd_density_threshold},
                        )
                    )

        # Purge stale trajectories to prevent unbounded memory growth
        self._trajectory_memory.cleanup_stale(
            current_time=current_time,
            max_age_seconds=max(60.0, self._config.max_trajectory_seconds * 2),
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return BehaviorResult(
            camera_id=cam_id,
            frame_id=track_result.frame_id,
            timestamp=current_time,
            frame_number=track_result.frame_number,
            dimensions=track_result.dimensions,
            observations=observations,
            events=events,
            density_map=zone_counts,
            processing_time_ms=elapsed_ms,
            metadata={"engine": "BehaviorEngine"},
        )


class MockBehaviorEngine(BehaviorEngine):
    """
    Mock Behavior Engine for deterministic unit testing.
    """

    def __init__(self, config: Optional[BehaviorConfig] = None) -> None:
        cfg = config if config is not None else BehaviorConfig(use_mock=True)
        super().__init__(cfg)
