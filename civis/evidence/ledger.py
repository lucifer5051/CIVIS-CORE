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
    Supports bounded in-memory working sets with explicit archive boundary tracking.
    """

    def __init__(self, enable_hash_chain: bool = True, max_records: Optional[int] = None) -> None:
        self.enable_hash_chain = enable_hash_chain
        self.max_records = max_records
        self._records: List[EvidenceRecord] = []
        self._last_hash: str = GENESIS_HASH
        self._archived_count: int = 0
        self._archived_boundary_hash: str = GENESIS_HASH

        # Fast lookup indexes
        self._by_id: Dict[str, EvidenceRecord] = {}
        self._by_camera: Dict[str, List[EvidenceRecord]] = {}
        self._by_entity: Dict[str, List[EvidenceRecord]] = {}
        self._by_track: Dict[Tuple[str, int], List[EvidenceRecord]] = {}
        self._by_stage: Dict[EvidenceStage, List[EvidenceRecord]] = {}

    @property
    def archived_count(self) -> int:
        return self._archived_count

    @property
    def archived_boundary_hash(self) -> str:
        return self._archived_boundary_hash

    @property
    def total_records_count(self) -> int:
        return self._archived_count + len(self._records)

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
        seq_num = self._archived_count + len(self._records)
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

        # Enforce bounded in-memory working set without altering cryptographic chain
        if self.max_records is not None and len(self._records) > self.max_records:
            excess = len(self._records) - self.max_records
            for old_rec in self._records[:excess]:
                self._by_id.pop(old_rec.evidence_id, None)
                if old_rec.camera_id in self._by_camera and old_rec in self._by_camera[old_rec.camera_id]:
                    self._by_camera[old_rec.camera_id].remove(old_rec)
                if old_rec.stage in self._by_stage and old_rec in self._by_stage[old_rec.stage]:
                    self._by_stage[old_rec.stage].remove(old_rec)
                if old_rec.global_entity_id and old_rec.global_entity_id in self._by_entity and old_rec in self._by_entity[old_rec.global_entity_id]:
                    self._by_entity[old_rec.global_entity_id].remove(old_rec)
                if old_rec.identity_id:
                    ident_key = f"ident_{old_rec.identity_id}"
                    if ident_key in self._by_entity and old_rec in self._by_entity[ident_key]:
                        self._by_entity[ident_key].remove(old_rec)
                if old_rec.track_id is not None:
                    trk_key = (old_rec.camera_id, old_rec.track_id)
                    if trk_key in self._by_track and old_rec in self._by_track[trk_key]:
                        self._by_track[trk_key].remove(old_rec)

                self._archived_boundary_hash = old_rec.record_hash
                self._archived_count += 1

            self._records = self._records[excess:]

        return record

    def get_record_by_id(self, evidence_id: str) -> Optional[EvidenceRecord]:
        return self._by_id.get(evidence_id)

    def get_all_records(self) -> List[EvidenceRecord]:
        return list(self._records)

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Traverses the entire ledger working set, verifying that every record's hash and
        hash-chain linkage match canonical mathematical hashes anchored from the archive root.
        """
        if not self._records:
            return True, None

        expected_prev_hash = (
            self._archived_boundary_hash if self._archived_count > 0 else GENESIS_HASH
        )

        for idx, record in enumerate(self._records):
            expected_seq = self._archived_count + idx
            if record.sequence_number != expected_seq:
                return (
                    False,
                    f"Integrity Violation: Sequence number mismatch at working set index {idx} (expected {expected_seq}, found {record.sequence_number})",
                )

            if self.enable_hash_chain:
                if record.previous_record_hash != expected_prev_hash:
                    return (
                        False,
                        f"Integrity Violation: Broken hash chain at working set index {idx} (evidence_id={record.evidence_id}). Expected previous hash {expected_prev_hash}, got {record.previous_record_hash}",
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
        self._archived_count = 0
        self._archived_boundary_hash = GENESIS_HASH
        self._by_id.clear()
        self._by_camera.clear()
        self._by_entity.clear()
        self._by_track.clear()
        self._by_stage.clear()
