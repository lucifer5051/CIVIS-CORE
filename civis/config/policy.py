from typing import Any, Dict, List, Optional, Tuple

from civis.config.models import PolicyRule


class PolicyManager:
    """
    Manages operational and security policies with deterministic priority-based evaluation.
    """

    def __init__(self, initial_policies: Optional[List[PolicyRule]] = None) -> None:
        self._policies: Dict[str, PolicyRule] = {}
        if initial_policies:
            for p in initial_policies:
                self.add_policy(p)

    def add_policy(self, policy: PolicyRule) -> None:
        self._policies[policy.policy_id] = policy

    def remove_policy(self, policy_id: str) -> bool:
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def get_policy(self, policy_id: str) -> Optional[PolicyRule]:
        return self._policies.get(policy_id)

    def list_policies(
        self,
        category: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[PolicyRule]:
        """Returns policies sorted by priority (lowest integer = highest priority)."""
        filtered = [
            p for p in self._policies.values()
            if (not enabled_only or p.enabled)
            and (category is None or p.category.lower() == category.lower())
        ]
        return sorted(filtered, key=lambda p: (p.priority, p.policy_id))

    def evaluate_policy(
        self,
        policy_id: str,
        context: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluates conditions of a specific policy against a runtime context dictionary.
        Returns: (is_matched, applied_parameters)
        """
        policy = self.get_policy(policy_id)
        if policy is None or not policy.enabled:
            return False, {}

        for cond_key, expected_val in policy.conditions.items():
            if cond_key not in context:
                return False, {}
            actual_val = context[cond_key]
            if actual_val != expected_val:
                return False, {}

        return True, dict(policy.parameters)
