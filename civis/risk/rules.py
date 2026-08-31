import logging
from typing import Any, Dict, List, Optional, Tuple

from civis.behavior.models import BehaviorEvent, BehaviorObservation
from civis.event_intelligence.models import CorrelatedEvent, EvidenceItem
from civis.identity.models import AssociatedIdentity, IdentityState
from civis.risk.models import ContextMultiplier, RiskContribution, RiskRule
from civis.tracking.models import TrackedObject

logger = logging.getLogger(__name__)


class RuleMatcher:
    """
    Evaluates configured RiskRules against active entity context (events, behaviors, identity, tracks)
    and generates typed RiskContributions with applied multipliers and full evidence references.
    """

    @classmethod
    def evaluate_rules(
        cls,
        rules: List[RiskRule],
        correlated_events: List[CorrelatedEvent],
        behavior_events: List[BehaviorEvent],
        behavior_obs: Optional[BehaviorObservation],
        identity: Optional[AssociatedIdentity],
        track: Optional[TrackedObject],
    ) -> List[RiskContribution]:
        """
        Evaluates sorted rules by priority (descending) and returns all triggered RiskContributions.
        """
        contributions: List[RiskContribution] = []
        # Deterministic evaluation by rule priority (descending), then rule_id
        sorted_rules = sorted(rules, key=lambda r: (r.priority, r.base_severity_score), reverse=True)

        for rule in sorted_rules:
            is_matched, matched_conf, evidence_refs = cls._match_rule_criteria(
                rule, correlated_events, behavior_events, behavior_obs, identity, track
            )

            if not is_matched:
                continue

            if matched_conf < rule.min_confidence:
                continue

            # Evaluate context multipliers
            applied_multipliers = []
            multiplier_product = 1.0

            for cm in rule.context_multipliers:
                applies, reason = cls._eval_context_multiplier(
                    cm, correlated_events, behavior_events, behavior_obs, identity, track
                )
                if applies:
                    multiplier_product *= cm.multiplier
                    applied_multipliers.append({
                        "condition_type": cm.condition_type,
                        "multiplier": cm.multiplier,
                        "description": reason or cm.description,
                    })

            base_score = rule.base_severity_score * rule.weight
            effective_score = min(100.0, max(0.0, base_score * multiplier_product))

            contrib = RiskContribution(
                source_type="rule_trigger",
                source_id=rule.rule_id,
                name=rule.name,
                base_score=base_score,
                confidence=min(1.0, max(0.0, matched_conf)),
                weight=rule.weight,
                applied_multipliers=applied_multipliers,
                effective_score=effective_score,
                evidence_references=evidence_refs,
            )
            contributions.append(contrib)

        return contributions

    @classmethod
    def _match_rule_criteria(
        cls,
        rule: RiskRule,
        correlated_events: List[CorrelatedEvent],
        behavior_events: List[BehaviorEvent],
        behavior_obs: Optional[BehaviorObservation],
        identity: Optional[AssociatedIdentity],
        track: Optional[TrackedObject],
    ) -> Tuple[bool, float, List[Any]]:
        """
        Checks if the required events, behaviors, and identity states match.
        """
        evidence_refs: List[Any] = []
        confidences: List[float] = []

        # 1. Required Correlated Events
        if rule.required_events:
            event_ids = {e.rule_id.lower() for e in correlated_events}
            event_names = {e.name.lower() for e in correlated_events}
            matched_any = False
            for req in rule.required_events:
                req_l = req.lower()
                for e in correlated_events:
                    if req_l in (e.rule_id.lower(), e.name.lower()):
                        matched_any = True
                        confidences.append(e.overall_confidence)
                        evidence_refs.extend(e.evidence_chain)
            if not matched_any:
                return False, 0.0, []

        # 2. Required Behaviors
        if rule.required_behaviors:
            beh_types = {e.event_type.lower() for e in behavior_events}
            if behavior_obs:
                beh_types.add(behavior_obs.state.value.lower())
            
            matched_any_beh = False
            for req_b in rule.required_behaviors:
                if req_b.lower() in beh_types:
                    matched_any_beh = True
                    # Add behavior events to evidence
                    for b_ev in behavior_events:
                        if b_ev.event_type.lower() == req_b.lower():
                            evidence_refs.append(b_ev)
                            confidences.append(0.85)
            if not matched_any_beh:
                return False, 0.0, []

        # 3. Required Identity States
        if rule.required_identity_states:
            current_state = identity.state.value.lower() if identity else "unknown"
            allowed_states = [s.lower() for s in rule.required_identity_states]
            if current_state not in allowed_states:
                return False, 0.0, []
            if identity:
                evidence_refs.append(identity)
                confidences.append(identity.association_confidence or identity.similarity_score or 0.8)
            else:
                confidences.append(0.7)

        # If no explicit requirements but rule exists, check if any correlated event or behavior occurred
        if not rule.required_events and not rule.required_behaviors and not rule.required_identity_states:
            if correlated_events:
                for e in correlated_events:
                    evidence_refs.extend(e.evidence_chain)
                    confidences.append(e.overall_confidence)
            elif behavior_events:
                for b_ev in behavior_events:
                    evidence_refs.append(b_ev)
                    confidences.append(0.8)
            else:
                return False, 0.0, []

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.8
        return True, avg_conf, evidence_refs

    @classmethod
    def _eval_context_multiplier(
        cls,
        cm: ContextMultiplier,
        correlated_events: List[CorrelatedEvent],
        behavior_events: List[BehaviorEvent],
        behavior_obs: Optional[BehaviorObservation],
        identity: Optional[AssociatedIdentity],
        track: Optional[TrackedObject],
    ) -> Tuple[bool, str]:
        """Evaluates whether a specific context multiplier condition holds."""
        ctype = cm.condition_type.upper()
        target = cm.target_value

        if ctype in ("ZONE_RESTRICTED", "ZONE_ID", "ZONE"):
            if behavior_obs and behavior_obs.current_zones:
                if isinstance(target, list):
                    if any(z in target for z in behavior_obs.current_zones):
                        return True, f"Located in restricted zone(s): {behavior_obs.current_zones}"
                elif target in behavior_obs.current_zones:
                    return True, f"Located in restricted zone: {target}"
            for b_ev in behavior_events:
                if b_ev.zone_id == target or (isinstance(target, list) and b_ev.zone_id in target):
                    return True, f"Zone violation in zone: {b_ev.zone_id}"

        elif ctype in ("UNKNOWN_IDENTITY", "IDENTITY_UNKNOWN"):
            if identity is None or identity.state in (IdentityState.UNKNOWN, IdentityState.UNVERIFIED):
                return True, "Subject identity is UNKNOWN or UNVERIFIED"

        elif ctype in ("PROXIMITY_HAZARD", "PROXIMITY_VIOLATION"):
            if behavior_obs and behavior_obs.proximity_track_ids:
                return True, f"Subject in close proximity with track(s): {behavior_obs.proximity_track_ids}"

        elif ctype in ("MIN_DWELL", "DWELL_TIME"):
            if behavior_obs and behavior_obs.dwell_time_sec >= float(target):
                return True, f"Dwell time {behavior_obs.dwell_time_sec:.1f}s exceeds threshold {target}s"

        elif ctype in ("MIN_SPEED", "HIGH_SPEED"):
            if behavior_obs and behavior_obs.speed_px_sec >= float(target):
                return True, f"Speed {behavior_obs.speed_px_sec:.1f}px/s exceeds threshold {target}px/s"

        return False, ""
