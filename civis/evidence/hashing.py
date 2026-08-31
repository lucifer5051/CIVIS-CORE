import hashlib
import json
import os
from typing import Any, Dict, Union


def canonical_json(data: Any) -> bytes:
    """
    Serializes data to deterministic canonical JSON bytes with sorted keys
    and compact formatting.
    """
    def _default_serializer(obj: Any) -> Any:
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        elif isinstance(obj, (set, tuple)):
            return list(obj)
        return str(obj)

    return json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        default=_default_serializer,
    ).encode("utf-8")


def compute_sha256(data: Union[str, bytes]) -> str:
    """Computes SHA-256 hex digest for given string or bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hash_file(filepath: str, block_size: int = 65536) -> str:
    """Computes streaming SHA-256 checksum for a file on disk."""
    if not os.path.isfile(filepath):
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            h.update(block)
    return h.hexdigest()


def compute_record_hash(
    sequence_number: int,
    stage: str,
    camera_id: str,
    frame_id: str,
    timestamp: float,
    payload: Dict[str, Any],
    previous_hash: str = "",
) -> str:
    """
    Computes cryptographic block-chain hash for an EvidenceRecord:
    Hash_n = SHA-256(previous_hash + sequence_number + stage + camera_id + frame_id + timestamp + canonical_payload)
    """
    canon_bytes = canonical_json(payload)
    header = f"{previous_hash}|{sequence_number}|{stage}|{camera_id}|{frame_id}|{timestamp:.6f}|".encode("utf-8")
    return compute_sha256(header + canon_bytes)
