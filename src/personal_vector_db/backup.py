"""Backup metadata that couples a Qdrant snapshot to its index contract."""

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from personal_vector_db.chunking import CHUNKING_VERSION
from personal_vector_db.contracts import EmbeddingManifest
from personal_vector_db.parsers.plain_text import PARSER_VERSION
from personal_vector_db.validation import validate_schema


@dataclass(frozen=True)
class BackupManifest:
    collection_name: str
    snapshot_name: str
    embedding_manifest_id: str
    model: str
    dimension: int
    metric: str
    parser_version: str
    chunking_version: str
    snapshot_checksum: str | None
    created_at: str
    parser_versions: list[str] | None = None
    corpus_checksum: str | None = None


def read_backup_manifest(path: Path) -> BackupManifest:
    """Load and validate a backup manifest before it is used for restore."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("backup manifest could not be read") from error
    if not isinstance(payload, dict):
        raise ValueError("backup manifest must be an object")
    validate_schema(payload, "backup-manifest.schema.json")
    return BackupManifest(**payload)


def write_backup_manifest(
    path: Path,
    *,
    collection_name: str,
    snapshot_name: str,
    snapshot_checksum: str | None = None,
    parser_versions: Sequence[str] | None = None,
    corpus_checksum: str | None = None,
    embedding: EmbeddingManifest,
) -> BackupManifest:
    versions = sorted(set(parser_versions or [PARSER_VERSION]))
    if not versions or any(not version.strip() for version in versions):
        raise ValueError("parser_versions must contain non-empty values")
    manifest = BackupManifest(
        collection_name=collection_name,
        snapshot_name=snapshot_name,
        embedding_manifest_id=embedding.manifest_id,
        model=embedding.model,
        dimension=embedding.dimension,
        metric=embedding.metric,
        parser_version=versions[0] if len(versions) == 1 else "mixed",
        parser_versions=versions,
        corpus_checksum=corpus_checksum,
        chunking_version=CHUNKING_VERSION,
        snapshot_checksum=snapshot_checksum,
        created_at=datetime.now(UTC).isoformat(),
    )
    validate_schema(asdict(manifest), "backup-manifest.schema.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
