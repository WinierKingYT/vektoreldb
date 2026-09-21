"""Structured, content-safe audit events for host applications to configure."""

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

LOGGER = logging.getLogger("personal_vector_db.audit")


def text_fingerprint(value: str) -> str:
    """Return a stable fingerprint without placing source text in logs."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def emit_audit_event(event: str, **fields: Any) -> None:
    """Emit one JSON event; callers must provide metadata, never raw content."""

    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    LOGGER.info(json.dumps(record, ensure_ascii=False, sort_keys=True))
