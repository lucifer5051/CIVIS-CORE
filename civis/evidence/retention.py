import time
from typing import List, Tuple

from civis.evidence.ledger import EvidenceLedger
from civis.evidence.models import CustodyAction, EvidenceRecord, RetentionPolicy


class RetentionManager:
    """
    Manages automated retention lifecycles, archiving, and lawful purging
    while preserving high-risk and sealed forensic records indefinitely.
    """

    def __init__(self, policy: RetentionPolicy) -> None:
        self.policy = policy

    def evaluate_retention(
        self,
        ledger: EvidenceLedger,
        current_time: float,
    ) -> Tuple[List[EvidenceRecord], List[EvidenceRecord]]:
        """
        Evaluates ledger records against retention policy.
        Returns: (records_to_retain, records_to_purge)
        """
        cutoff_time = current_time - (self.policy.max_retention_days * 86400.0)
        to_retain: List[EvidenceRecord] = []
        to_purge: List[EvidenceRecord] = []

        for record in ledger.get_all_records():
            # Never purge sealed or high-risk records if configured
            if record.is_sealed or (self.policy.retain_high_risk_indefinitely and record.is_high_risk):
                to_retain.append(record)
                continue

            if record.timestamp < cutoff_time:
                to_purge.append(record)
            else:
                to_retain.append(record)

        return to_retain, to_purge
