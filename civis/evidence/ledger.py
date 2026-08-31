import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from civis.evidence.custody import ChainOfCustodyManager
from civis.evidence.hashing import compute_record_hash
from civis.evidence.models import EvidenceRecord, EvidenceStage

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64


class EvidenceLedger:
    """
    Append-only, cryptographically hash-chained evidence ledger.
    Guarantees mathematical tamper-evidence and fast multi-indexed forensic queries.
    """

    def __init__(self, enable_hash_chain: bool = True) -> None:
        self.enable_hash_chain = enable_hash_chain
        self._records: List[EvidenceRecord] = []
        self._last_hash: str = GENESIS_HASH

        # Fast lookup indexes
        self._by_id: Dict[str, EvidenceRecord] = {}
        self._by_camera: Dict[str, List[EvidenceRecord]] = {}
        self._by_entity: Dict[str, List[EvidenceRecord]] = {}
        self._by_track: Dict[Tuple[str, int], List[EvidenceRecord]] = {}
        self._by_stage: Dict[EvidenceStage, List[EvidenceRecord]] = {}

    def append(
        self,
        evidence_id: str,
        stage: EvidenceStage,
        camera_id: str,
        frame_id: str,
        frame_number: int,
        timestamp: float,
        payload: Dict[str, Any],
        track_id: Optional[int] = None,
        global_entity_id: Optional[str] = None,
        identity_id: Optional[str] = None,
        risk_score: Optional[float] = None,
        severity: Optional[str] = None,
        media_references: Optional[List[Dict[str, Any]]] = None,
        parent_evidence_ids: Optional[List[str]] = None,
        actor: str = "CIVIS_PIPELINE",
    ) -> EvidenceRecord:
        """Appends a new evidence record and updates the cryptographic hash chain."""
        seq_num = len(self._records)
        prev_hash = self._last_hash if self.enable_hash_chain else ""

        rec_hash = compute_record_hash(
            sequence_number=seq_num,
            stage=stage.value,
            camera_id=camera_id,
            frame_id=frame_id,
            timestamp=timestamp,
            payload=payload,
            previous_hash=prev_hash,
        )

        custody_entry = ChainOfCustodyManager.create_initial_entry(
            evidence_id=evidence_id,
            actor=actor,
            record_hash=rec_hash,
            timestamp=timestamp,
        )

        record = EvidenceRecord(
            evidence_id=evidence_id,
            sequence_number=seq_num,
            stage=stage,
            camera_id=camera_id,
            frame_id=frame_id,
            frame_number=frame_number,
            timestamp=timestamp,
            track_id=track_id,
            global_entity_id=global_entity_id,
            identity_id=identity_id,
            risk_score=risk_score,
            severity=severity,
            payload=payload,
            media_references=media_references or [],
            parent_evidence_ids=parent_evidence_ids or [],
            previous_record_hash=prev_hash,
            record_hash=rec_hash,
            custody_trail=[custody_entry],
        )

        self._records.append(record)
        self._last_hash = rec_hash

        # Index record
        self._by_id[record.evidence_id] = record
        self._by_camera.setdefault(camera_id, []).append(record)
        self._by_stage.setdefault(stage, []).append(record)

        if global_entity_id:
            self._by_entity.setdefault(global_entity_id, []).append(record)
        if identity_id and identity_id not in ("UNKNOWN", "", "None"):
            self._by_entity.setdefault(f"ident_{identity_id}", []).append(record)
        if track_id is not None:
            self._by_track.setdefault((camera_id, track_id), []).append(record)

        return record

    def get_record_by_id(self, evidence_id: str) -> Optional[EvidenceRecord]:
        return self._by_id.get(evidence_id)

    def get_all_records(self) -> List[EvidenceRecord]:
        return list(self._records)

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Traverses the entire ledger, verifying that every record's hash and
        hash-chain linkage match canonical mathematical hashes.
        """
        expected_prev_hash = GENESIS_HASH

        for idx, record in enumerate(self._records):
            if record.sequence_number != idx:
                return (
                    False,
                    f"Integrity Violation: Sequence number mismatch at index {idx} (found {record.sequence_number})",
                )

            if self.enable_hash_chain:
                if record.previous_record_hash != expected_prev_hash:
                    return (
                        False,
                        f"Integrity Violation: Broken hash chain at index {idx} (evidence_id={record.evidence_id}). Expected previous hash {expected_prev_hash}, got {record.previous_record_hash}",
                    )

            recalculated_hash = compute_record_hash(
                sequence_number=record.sequence_number,
                stage=record.stage.value,
                camera_id=record.camera_id,
                frame_id=record.frame_id,
                timestamp=record.timestamp,
                payload=record.payload,
                previous_hash=expected_prev_hash if self.enable_hash_chain else "",
            )

            if recalculated_hash != record.record_hash:
                return (
                    False,
                    f"Integrity Violation: Tampered record content at index {idx} (evidence_id={record.evidence_id}). Hash mismatch.",
                )

            expected_prev_hash = record.record_hash

        return True, None

    def query(
        self,
        camera_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        track_id: Optional[int] = None,
        stage: Optional[EvidenceStage] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        min_severity: Optional[str] = None,
    ) -> List[EvidenceRecord]:
        """Queries ledger with multi-parameter filtering."""
        candidates = self._records

        if camera_id and camera_id in self._by_camera:
            candidates = self._by_camera[camera_id]
        elif stage and stage in self._by_stage:
            candidates = self._by_stage[stage]

        severity_rank = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        min_rank = severity_rank.get(min_severity.lower(), 0) if min_severity else 0

        results = []
        for r in candidates:
            if camera_id and r.camera_id != camera_id:
                continue
            if stage and r.stage != stage:
                continue
            if track_id is not None and r.track_id != track_id:
                continue
            if entity_id:
                ent_match = (
                    r.global_entity_id == entity_id
                    or r.identity_id == entity_id
                    or f"ident_{r.identity_id}" == entity_id
                )
                if not ent_match:
                    continue
            if start_time is not None and r.timestamp < start_time:
                continue
            if end_time is not None and r.timestamp > end_time:
                continue
            if min_severity:
                r_sev = r.severity.lower() if r.severity else "info"
                if severity_rank.get(r_sev, 0) < min_rank:
                    continue

            results.append(r)

        return results

    def reset(self) -> None:
        self._records.clear()
        self._last_hash = GENESIS_HASH
        self._by_id.clear()
        self._by_camera.clear()
        self._by_entity.clear()
        self._by_track.clear()
        self._by_stage.clear()
