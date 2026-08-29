import logging
from typing import Any, List, Optional, Tuple

from civis.event_intelligence.correlation import TrackTemporalObservationBuffer
from civis.event_intelligence.models import (
    Condition,
    EventRule,
    EvidenceItem,
    LogicOperator,
)

logger = logging.getLogger(__name__)


def _compare_value(actual: Any, target: Any, op: str) -> bool:
    if op == "==":
        return actual == target
    elif op == "!=":
        return actual != target
    elif op == ">=":
        return actual >= target
    elif op == "<=":
        return actual <= target
    elif op == ">":
        return actual > target
    elif op == "<":
        return actual < target
    elif op == "IN":
        return target in actual if isinstance(actual, (list, set, tuple, str)) else False
    return False


class RuleEvaluator:
    """
    Evaluates configurable, data-driven EventRules against temporal track observation buffers.
    Supports AND, OR, and SEQUENCE logic operators.
    """

    @staticmethod
    def evaluate_rule(
        rule: EventRule,
        buffer: TrackTemporalObservationBuffer,
        current_time: float,
    ) -> Tuple[bool, List[EvidenceItem]]:
        if not rule.conditions:
            return False, []

        satisfied_evidences: List[EvidenceItem] = []

        if rule.logic_operator == LogicOperator.SEQUENCE:
            return RuleEvaluator._evaluate_sequence(rule, buffer, current_time)

        condition_results = []
        for cond in rule.conditions:
            is_met, ev = RuleEvaluator._eval_condition(cond, buffer, current_time)
            condition_results.append(is_met)
            if is_met and ev is not None:
                satisfied_evidences.append(ev)

        if rule.logic_operator == LogicOperator.AND:
            rule_passed = all(condition_results)
        elif rule.logic_operator == LogicOperator.OR:
            rule_passed = any(condition_results)
        else:
            rule_passed = all(condition_results)

        return rule_passed, satisfied_evidences

    @staticmethod
    def _eval_condition(
        cond: Condition,
        buffer: TrackTemporalObservationBuffer,
        current_time: float,
    ) -> Tuple[bool, Optional[EvidenceItem]]:
        ctype = cond.condition_type

        if ctype == "BEHAVIOR_TYPE":
            for ts, obs in reversed(buffer.behavior_observations):
                if _compare_value(obs.state.value, cond.target_value, cond.operator):
                    return True, EvidenceItem(
                        evidence_type="BEHAVIOR_TYPE",
                        source_module="behavior",
                        timestamp=ts,
                        camera_id=buffer.camera_id,
                        track_id=buffer.track_id,
                        identity_id=obs.identity_id,
                        description=f"Behavior state is '{obs.state.value}'",
                        confidence=1.0,
                    )
            for ts, evt in reversed(buffer.behavior_events):
                if _compare_value(evt.event_type, cond.target_value, cond.operator):
                    return True, EvidenceItem(
                        evidence_type="BEHAVIOR_EVENT",
                        source_module="behavior",
                        timestamp=ts,
                        camera_id=buffer.camera_id,
                        track_id=buffer.track_id,
                        description=f"Behavior event '{evt.event_type}' triggered",
                        confidence=1.0,
                    )

        elif ctype == "IDENTITY_STATE":
            for ts, ident in reversed(buffer.identity_history):
                if _compare_value(ident.state.value, cond.target_value, cond.operator):
                    return True, EvidenceItem(
                        evidence_type="IDENTITY_STATE",
                        source_module="identity",
                        timestamp=ts,
                        camera_id=buffer.camera_id,
                        track_id=buffer.track_id,
                        identity_id=ident.identity_id,
                        description=f"Identity state is '{ident.state.value}' (ID: {ident.identity_id})",
                        confidence=ident.association_confidence,
                    )

        elif ctype == "ZONE_ID":
            for ts, obs in reversed(buffer.behavior_observations):
                if any(_compare_value(z, cond.target_value, cond.operator) for z in obs.current_zones):
                    return True, EvidenceItem(
                        evidence_type="ZONE_ID",
                        source_module="behavior",
                        timestamp=ts,
                        camera_id=buffer.camera_id,
                        track_id=buffer.track_id,
                        description=f"Present inside zone '{cond.target_value}'",
                        confidence=1.0,
                    )

        elif ctype == "DWELL_TIME":
            for ts, obs in reversed(buffer.behavior_observations):
                if _compare_value(obs.dwell_time_sec, cond.target_value, cond.operator):
                    return True, EvidenceItem(
                        evidence_type="DWELL_TIME",
                        source_module="behavior",
                        timestamp=ts,
                        camera_id=buffer.camera_id,
                        track_id=buffer.track_id,
                        description=f"Dwell duration is {obs.dwell_time_sec:.1f}s ({cond.operator} {cond.target_value}s)",
                        confidence=1.0,
                    )

        return False, None

    @staticmethod
    def _evaluate_sequence(
        rule: EventRule,
        buffer: TrackTemporalObservationBuffer,
        current_time: float,
    ) -> Tuple[bool, List[EvidenceItem]]:
        evidences: List[EvidenceItem] = []
        last_matched_ts = 0.0

        for cond in rule.conditions:
            is_met, ev = RuleEvaluator._eval_condition(cond, buffer, current_time)
            if not is_met or ev is None:
                return False, []
            if ev.timestamp < last_matched_ts:
                return False, []
            last_matched_ts = ev.timestamp
            evidences.append(ev)

        return True, evidences
