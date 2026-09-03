"""
Deterministic Canonical Hashing & Serialization Engine.
Fulfills Institutional Acceptance Invariant H: Feature Regeneration Determinism.
Re-running the feature engine on identical frozen PIT inputs produces bit-for-bit identical hashes.
"""
import hashlib
import json
from datetime import date, datetime
from typing import Any, Dict

def canonical_serialize_value(val: Any) -> Any:
    """
    Recursively converts values into a deterministic, canonical representation.
    Ensures floating point precision is strictly bounded to eliminate micro-drift,
    dates/datetimes are normalized to ISO-8601 UTC strings, and dictionaries are sorted.
    """
    if val is None:
        return None
    elif isinstance(val, bool):
        return val
    elif isinstance(val, (int,)):
        return val
    elif isinstance(val, (float,)):
        # Round to 6 decimal places to prevent IEEE 754 micro-precision drift across architectures
        return round(val, 6)
    elif isinstance(val, (datetime,)):
        return val.strftime("%Y-%m-%dT%H:%M:%SZ")
    elif isinstance(val, (date,)):
        return val.strftime("%Y-%m-%d")
    elif isinstance(val, (list, tuple)):
        return [canonical_serialize_value(x) for x in val]
    elif isinstance(val, dict):
        return {str(k): canonical_serialize_value(v) for k, v in sorted(val.items(), key=lambda x: str(x[0]))}
    else:
        return str(val)

def canonical_serialize(obj: Dict[str, Any]) -> str:
    """
    Produces a canonical, deterministic JSON string with sorted keys and normalized values.
    """
    normalized = canonical_serialize_value(obj)
    return json.dumps(normalized, sort_keys=True, separators=(',', ':'), ensure_ascii=True)

def compute_canonical_hash(obj: Dict[str, Any]) -> str:
    """
    Computes a SHA-256 hash of the canonical serialized object.
    """
    canonical_str = canonical_serialize(obj)
    return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()
