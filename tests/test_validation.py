import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from personal_vector_db.validation import PACKAGE_SCHEMA_DIR, validate_schema


def test_openapi_contract_is_valid_yaml_with_v1_paths() -> None:
    document = yaml.safe_load(Path("openapi.yaml").read_text(encoding="utf-8"))

    assert document["openapi"].startswith("3.")
    assert {
        "/v1/health",
        "/v1/search",
        "/v1/documents:ingest",
        "/v1/documents/{document_id}",
        "/v1/documents/{document_id}:reindex",
    } <= set(document["paths"])
    search_request = document["components"]["schemas"]["SearchRequest"]
    assert search_request["additionalProperties"] is False
    assert {
        "document_ids",
        "source_uris",
        "source_types",
        "titles",
        "rerank",
    } <= set(search_request["properties"])
    stages = document["components"]["schemas"]["SearchResult"]["properties"][
        "retrieval_stage"
    ]["enum"]
    assert {"dense", "hybrid", "late_interaction", "dense+rerank"} <= set(stages)


def test_packaged_schemas_match_repository_canonical_schemas() -> None:
    repository_schema_dir = Path("schemas")
    for schema_name in sorted(path.name for path in repository_schema_dir.glob("*.json")):
        packaged = json.loads(PACKAGE_SCHEMA_DIR.joinpath(schema_name).read_text(encoding="utf-8"))
        canonical = json.loads(
            repository_schema_dir.joinpath(schema_name).read_text(encoding="utf-8")
        )
        assert packaged == canonical


def test_document_schema_accepts_canonical_metadata() -> None:
    now = datetime.now(UTC).isoformat()
    validate_schema(
        {
            "document_id": "doc_abc",
            "source_uri": "file:///note.md",
            "source_type": "markdown",
            "title": "Note",
            "owner_id": "me",
            "visibility": "private",
            "document_status": "parsed",
            "content_hash": "sha256:" + "a" * 64,
            "parser_version": "plain-text-v1",
            "created_at": now,
            "updated_at": now,
        },
        "document.schema.json",
    )


def test_document_schema_accepts_xml_source_type() -> None:
    now = datetime.now(UTC).isoformat()
    validate_schema(
        {
            "document_id": "doc_xml",
            "source_uri": "file:///export.xml",
            "source_type": "xml",
            "title": "XML export",
            "owner_id": "me",
            "visibility": "private",
            "document_status": "parsed",
            "content_hash": "sha256:" + "b" * 64,
            "parser_version": "xml-v1",
            "created_at": now,
            "updated_at": now,
        },
        "document.schema.json",
    )


def test_chunk_schema_rejects_unknown_fields() -> None:
    try:
        validate_schema(
            {
                "document_id": "doc_abc",
                "chunk_id": "chunk_1",
                "chunk_index": 0,
                "text": "İçerik",
                "owner_id": "me",
                "document_status": "active",
                "embedding_manifest_id": "manifest",
                "chunking_version": "v1",
                "unknown": True,
            },
            "chunk-payload.schema.json",
        )
    except ValueError as error:
        assert "unknown" in str(error)
    else:
        raise AssertionError("unknown payload fields must be rejected")
