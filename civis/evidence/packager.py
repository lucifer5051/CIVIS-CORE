import json
import os
import time
import uuid
from typing import Dict, List, Optional, Tuple

from civis.evidence.hashing import canonical_json, compute_sha256, hash_file
from civis.evidence.models import ForensicPackageManifest, InvestigationTimeline


class ForensicPackager:
    """
    Exports self-contained, tamper-verifiable forensic packages
    conforming to RFC 8493 BagIt manifest standards with SHA-256 checksums.
    """

    @classmethod
    def export_package(
        cls,
        timeline: InvestigationTimeline,
        target_directory: str,
        root_ledger_hash: str = "",
    ) -> ForensicPackageManifest:
        os.makedirs(target_directory, exist_ok=True)
        data_dir = os.path.join(target_directory, "data")
        os.makedirs(data_dir, exist_ok=True)

        package_id = f"pkg_{uuid.uuid4().hex[:8]}"
        creation_time = time.time()

        # 1. Write timeline.json
        timeline_path = os.path.join(data_dir, "timeline.json")
        timeline_data = {
            "timeline_id": timeline.timeline_id,
            "title": timeline.title,
            "start_timestamp": timeline.start_timestamp,
            "end_timestamp": timeline.end_timestamp,
            "involved_cameras": timeline.involved_cameras,
            "involved_entities": timeline.involved_entities,
            "total_records": timeline.total_records,
            "summary": timeline.summary,
            "records": [
                {
                    "evidence_id": r.evidence_id,
                    "sequence_number": r.sequence_number,
                    "stage": r.stage.value,
                    "camera_id": r.camera_id,
                    "frame_id": r.frame_id,
                    "frame_number": r.frame_number,
                    "timestamp": r.timestamp,
                    "track_id": r.track_id,
                    "global_entity_id": r.global_entity_id,
                    "identity_id": r.identity_id,
                    "risk_score": r.risk_score,
                    "severity": r.severity,
                    "payload": r.payload,
                    "media_references": r.media_references,
                    "parent_evidence_ids": r.parent_evidence_ids,
                    "previous_record_hash": r.previous_record_hash,
                    "record_hash": r.record_hash,
                    "is_sealed": r.is_sealed,
                }
                for r in timeline.records
            ],
        }
        with open(timeline_path, "wb") as f:
            f.write(canonical_json(timeline_data))

        # 2. Write chain_of_custody.json
        coc_path = os.path.join(data_dir, "chain_of_custody.json")
        coc_entries = []
        for r in timeline.records:
            for c in r.custody_trail:
                coc_entries.append({
                    "custody_id": c.custody_id,
                    "evidence_id": c.evidence_id,
                    "timestamp": c.timestamp,
                    "action": c.action.value,
                    "actor": c.actor,
                    "prior_hash": c.prior_hash,
                    "current_hash": c.current_hash,
                    "notes": c.notes,
                })
        with open(coc_path, "wb") as f:
            f.write(canonical_json(coc_entries))

        # 3. Write bagit.txt
        bagit_path = os.path.join(target_directory, "bagit.txt")
        with open(bagit_path, "w", encoding="utf-8") as f:
            f.write("BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n")

        # 4. Generate manifest-sha256.txt (RFC 8493)
        checksums: Dict[str, str] = {}
        manifest_path = os.path.join(target_directory, "manifest-sha256.txt")

        files_to_hash = [
            ("data/timeline.json", timeline_path),
            ("data/chain_of_custody.json", coc_path),
        ]

        with open(manifest_path, "w", encoding="utf-8") as mf:
            for rel_path, full_path in files_to_hash:
                h = hash_file(full_path)
                checksums[rel_path] = h
                mf.write(f"{h}  {rel_path}\n")

        return ForensicPackageManifest(
            package_id=package_id,
            creation_timestamp=creation_time,
            total_files=len(files_to_hash),
            total_evidence_records=timeline.total_records,
            root_ledger_hash=root_ledger_hash,
            file_checksums=checksums,
            is_valid=True,
        )

    @classmethod
    def verify_package(cls, package_directory: str) -> Tuple[bool, Optional[str]]:
        """Verifies package integrity against manifest-sha256.txt."""
        manifest_path = os.path.join(package_directory, "manifest-sha256.txt")
        if not os.path.isfile(manifest_path):
            return False, "Missing manifest-sha256.txt"

        with open(manifest_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or "  " not in line:
                continue
            expected_hash, rel_path = line.split("  ", 1)
            full_path = os.path.join(package_directory, rel_path.replace("/", os.sep))
            if not os.path.isfile(full_path):
                return False, f"Missing payload file: {rel_path}"

            computed_hash = hash_file(full_path)
            if computed_hash != expected_hash:
                return False, f"Checksum mismatch on {rel_path}: expected {expected_hash}, got {computed_hash}"

        return True, None
