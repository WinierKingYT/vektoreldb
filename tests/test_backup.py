from pathlib import Path

from personal_vector_db.backup import read_backup_manifest, write_backup_manifest
from personal_vector_db.contracts import EmbeddingManifest


def test_backup_manifest_preserves_collection_and_embedding_contract(tmp_path: Path) -> None:
    embedding = EmbeddingManifest("local", "model", "r1", 768, "cosine", True)
    path = tmp_path / "manifests" / "backup.json"

    manifest = write_backup_manifest(
        path,
        collection_name="personal_documents_v1",
        snapshot_name="snapshot-1",
        embedding=embedding,
    )

    assert manifest.collection_name == "personal_documents_v1"
    assert manifest.snapshot_name == "snapshot-1"
    assert manifest.parser_version == "plain-text-v1"
    assert manifest.parser_versions == ["plain-text-v1"]
    assert manifest.corpus_checksum is None
    assert manifest.chunking_version == "paragraph-pack-v2"
    assert manifest.snapshot_checksum is None
    assert path.exists()
    assert '"dimension": 768' in path.read_text(encoding="utf-8")
    loaded = read_backup_manifest(path)
    assert loaded == manifest


def test_backup_manifest_loader_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("not-json", encoding="utf-8")

    try:
        read_backup_manifest(path)
    except ValueError as error:
        assert "could not be read" in str(error)
    else:
        raise AssertionError("invalid backup manifest must be rejected")


def test_backup_manifest_records_mixed_parser_versions(tmp_path: Path) -> None:
    embedding = EmbeddingManifest("local", "model", "r1", 768, "cosine", True)
    manifest = write_backup_manifest(
        tmp_path / "mixed.json",
        collection_name="personal_documents_v1",
        snapshot_name="snapshot-mixed",
        parser_versions=["docx-v2", "html-v2", "plain-text-v1"],
        embedding=embedding,
    )

    assert manifest.parser_version == "mixed"
    assert manifest.parser_versions == ["docx-v2", "html-v2", "plain-text-v1"]


def test_backup_manifest_rejects_schema_drift(monkeypatch, tmp_path: Path) -> None:
    embedding = EmbeddingManifest("local", "model", "r1", 768, "cosine", True)

    def fail_validation(*args, **kwargs):
        raise ValueError("schema validation failed")

    monkeypatch.setattr("personal_vector_db.backup.validate_schema", fail_validation)
    try:
        write_backup_manifest(
            tmp_path / "manifest.json",
            collection_name="collection",
            snapshot_name="snapshot",
            embedding=embedding,
        )
    except ValueError as error:
        assert "schema" in str(error)
    else:
        raise AssertionError("backup manifest schema drift must be rejected")
