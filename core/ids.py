import uuid
import hashlib
from typing import Union


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    unique_id = str(uuid.uuid4())[:8]
    return f"{prefix}_{unique_id}" if prefix else unique_id


def generate_evidence_id(source_type: str, index: int = None) -> str:
    """Generate ID for evidence items."""
    if index is not None:
        return f"{source_type}_{index}"
    return generate_id(source_type)


def generate_claim_id(index: int = None) -> str:
    """Generate ID for claims."""
    if index is not None:
        return f"c{index}"
    return generate_id("c")


def generate_step_id(index: int = None) -> str:
    """Generate ID for plan steps."""
    if index is not None:
        return f"s{index}"
    return generate_id("s")


def generate_action_id() -> str:
    """Generate ID for action logs."""
    return generate_id("act")


def generate_fingerprint(text: str, url: str = "") -> str:
    """Generate fingerprint for deduplication."""
    content = f"{url}|{text}".encode('utf-8')
    return hashlib.md5(content).hexdigest()[:16]