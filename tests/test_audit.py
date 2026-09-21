import json
import logging

from personal_vector_db.audit import emit_audit_event, text_fingerprint


def test_audit_event_is_json_and_does_not_need_raw_text(caplog) -> None:
    sensitive = "gizli kişisel not"
    with caplog.at_level(logging.INFO, logger="personal_vector_db.audit"):
        emit_audit_event("retrieval_completed", query_sha256=text_fingerprint(sensitive))

    record = json.loads(caplog.records[-1].message)
    assert record["event"] == "retrieval_completed"
    assert sensitive not in caplog.text
    assert record["query_sha256"] == text_fingerprint(sensitive)
