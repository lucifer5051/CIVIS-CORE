import time
import uuid
from typing import List, Optional

from civis.evidence.hashing import compute_sha256
from civis.evidence.models import CustodyAction, CustodyEntry, EvidenceRecord


class ChainOfCustodyManager:
    """
    Manages chain-of-custody lifecycle transitions and non-repudiation audit trails.
    """

    @classmethod
    def create_initial_entry(
        cls,
        evidence_id: str,
        actor: str,
        record_hash: str,
        timestamp: float,
    ) -> CustodyEntry:
        """Creates the initial CAPTURED custody entry for newly minted evidence."""
        custody_id = f"coc_{uuid.uuid4().hex[:8]}"
        entry = CustodyEntry(
            custody_id=custody_id,
            evidence_id=evidence_id,
            timestamp=timestamp,
            action=CustodyAction.CAPTURED,
            actor=actor,
            prior_hash="GENESIS",
            current_hash=record_hash,
            notes="Initial digital evidence acquisition",
        )
        return entry

    @classmethod
    def record_action(
        cls,
        record: EvidenceRecord,
        action: CustodyAction,
        actor: str,
        notes: str = "",
        timestamp: Optional[float] = None,
    ) -> CustodyEntry:
        """
        Appends an immutable chain-of-custody lifecycle transition.
        """
        ts = timestamp if timestamp is not None else time.time()
        custody_id = f"coc_{uuid.uuid4().hex[:8]}"
        prior_hash = record.record_hash

        if action == CustodyAction.SEALED:
            record.is_sealed = True

        entry_data = f"{custody_id}|{record.evidence_id}|{ts:.6f}|{action.value}|{actor}|{prior_hash}|{notes}"
        action_hash = compute_sha256(entry_data)

        entry = CustodyEntry(
            custody_id=custody_id,
            evidence_id=record.evidence_id,
            timestamp=ts,
            action=action,
            actor=actor,
            prior_hash=prior_hash,
            current_hash=action_hash,
            notes=notes,
        )
        record.custody_trail.append(entry)
        return entry
