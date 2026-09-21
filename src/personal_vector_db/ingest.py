"""First vertical ingest flow: parse, chunk, embed and upsert."""

import re
import uuid
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from time import perf_counter

from qdrant_client.http import models

from personal_vector_db.audit import emit_audit_event
from personal_vector_db.chunking import Chunk, chunk_document
from personal_vector_db.contracts import EmbeddingProvider, VectorStore
from personal_vector_db.parsers import parse_source
from personal_vector_db.security import (
    SUPPORTED_SUFFIXES,
    detect_prompt_injection,
    is_excluded_directory,
    validate_source_path,
)
from personal_vector_db.validation import validate_schema

POINT_NAMESPACE = uuid.UUID("3f8c8bb3-4da0-4f4a-8c80-eec80c2bb0a0")
DOCUMENT_ID_PATTERN = re.compile(r"^doc_[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class IngestResult:
    document_id: str
    chunk_count: int
    embedding_manifest_id: str


@dataclass(frozen=True)
class IngestFailure:
    relative_path: str
    error_type: str


@dataclass(frozen=True)
class DirectoryIngestResult:
    indexed: tuple[IngestResult, ...]
    failures: tuple[IngestFailure, ...]


def point_id_for_chunk(chunk_id: str) -> str:
    """Return a stable UUID accepted by Qdrant while retaining chunk_id in payload."""

    return str(uuid.uuid5(POINT_NAMESPACE, chunk_id))


def validate_document_id(document_id: str) -> str:
    if not DOCUMENT_ID_PATTERN.fullmatch(document_id):
        raise ValueError("invalid document_id")
    return document_id


class IngestService:
    def __init__(
        self,
        provider: EmbeddingProvider,
        store: VectorStore,
        *,
        source_root: Path | None = None,
        max_source_bytes: int = 10_000_000,
        max_directory_files: int = 5_000,
        max_directory_bytes: int = 1_000_000_000,
    ) -> None:
        if max_source_bytes < 1:
            raise ValueError("max_source_bytes must be positive")
        if (
            isinstance(max_directory_files, bool)
            or not isinstance(max_directory_files, int)
            or max_directory_files < 1
        ):
            raise ValueError("max_directory_files must be a positive integer")
        if (
            isinstance(max_directory_bytes, bool)
            or not isinstance(max_directory_bytes, int)
            or max_directory_bytes < 1
        ):
            raise ValueError("max_directory_bytes must be a positive integer")
        self.provider = provider
        self.store = store
        self.source_root = source_root
        self.max_source_bytes = max_source_bytes
        self.max_directory_files = max_directory_files
        self.max_directory_bytes = max_directory_bytes

    def ingest_file(self, path: Path) -> IngestResult:
        if self.source_root is not None:
            path = validate_source_path(
                path, self.source_root, max_bytes=self.max_source_bytes
            )
        else:
            self._validate_unrooted_source_size(path)
        result, points = self._prepare_file(path)
        self._store_replacement(result.document_id, points)
        self._emit_ingest_event(result)
        return result

    def ingest_directory(self, path: Path) -> DirectoryIngestResult:
        """Ingest supported files in deterministic order while isolating failures."""

        resolved_root = path.resolve()
        if self.source_root is not None:
            configured_root = self.source_root.resolve()
            try:
                resolved_root.relative_to(configured_root)
            except ValueError as error:
                raise ValueError(
                    "source directory is outside the configured source root"
                ) from error
        if not resolved_root.is_dir():
            raise ValueError("source directory is not a directory")
        candidates: list[tuple[str, Path]] = []
        failures: list[IngestFailure] = []
        total_source_bytes = 0
        candidate_count = 0
        validation_root = self.source_root or resolved_root
        for candidate in resolved_root.rglob("*"):
            if (
                not candidate.is_file()
                or is_excluded_directory(candidate, resolved_root)
                or candidate.suffix.lower() not in SUPPORTED_SUFFIXES
            ):
                continue
            candidate_count += 1
            if candidate_count > self.max_directory_files:
                raise ValueError("directory exceeds the configured source file limit")
            relative_path = candidate.relative_to(resolved_root).as_posix()
            try:
                validated_path = validate_source_path(
                    candidate, validation_root, max_bytes=self.max_source_bytes
                )
                source_size = validated_path.stat().st_size
            except Exception as error:
                failures.append(
                    IngestFailure(relative_path=relative_path, error_type=type(error).__name__)
                )
                continue
            if total_source_bytes + source_size > self.max_directory_bytes:
                raise ValueError("directory exceeds the configured total source bytes limit")
            total_source_bytes += source_size
            candidates.append((relative_path, validated_path))

        indexed: list[IngestResult] = []
        for relative_path, source_path in sorted(candidates, key=lambda item: item[0]):
            try:
                indexed.append(self.ingest_file(source_path))
            except Exception as error:
                failures.append(
                    IngestFailure(relative_path=relative_path, error_type=type(error).__name__)
                )
        return DirectoryIngestResult(tuple(indexed), tuple(failures))

    def _prepare_file(
        self, path: Path, *, document: object | None = None
    ) -> tuple[IngestResult, list[models.PointStruct]]:
        ensure_collection = getattr(self.store, "ensure_collection", None)
        if ensure_collection is not None:
            ensure_collection(self.provider.manifest.dimension)
        ensure_manifest = getattr(self.store, "ensure_manifest", None)
        if ensure_manifest is not None:
            ensure_manifest(self.provider.manifest.manifest_id)
        if document is None:
            document = parse_source(path, max_bytes=self.max_source_bytes)
        validate_schema(
            document.model_dump(mode="json", exclude={"sections"}), "document.schema.json"
        )
        chunks = chunk_document(document)
        embedding_started = perf_counter()
        vectors = self.provider.embed_documents([chunk.text for chunk in chunks])
        emit_audit_event(
            "embedding_completed",
            stage="ingest",
            item_count=len(chunks),
            input_chars=sum(len(chunk.text) for chunk in chunks),
            embedding_manifest_id=self.provider.manifest.manifest_id,
            latency_ms=round((perf_counter() - embedding_started) * 1000, 3),
        )
        if len(vectors) != len(chunks):
            raise ValueError("embedding count does not match chunk count")

        points = [self._point(document, chunk, vector) for chunk, vector in zip(chunks, vectors)]
        return (
            IngestResult(
                document_id=document.document_id,
                chunk_count=len(chunks),
                embedding_manifest_id=self.provider.manifest.manifest_id,
            ),
            points,
        )

    def _emit_ingest_event(self, result: IngestResult) -> None:
        emit_audit_event(
            "document_ingested",
            document_id=result.document_id,
            chunk_count=result.chunk_count,
            embedding_manifest_id=result.embedding_manifest_id,
        )

    def delete_document(self, document_id: str) -> None:
        validate_document_id(document_id)
        self.store.delete_document(document_id)
        emit_audit_event("document_deleted", document_id=document_id)

    def reindex_file(self, path: Path, document_id: str | None = None) -> IngestResult:
        validated_path = path
        if self.source_root is not None:
            validated_path = validate_source_path(
                path, self.source_root, max_bytes=self.max_source_bytes
            )
        else:
            self._validate_unrooted_source_size(path)
        # Parse and derive the identity before deleting so malformed or
        # mismatched updates cannot remove the last known-good version.
        document = parse_source(validated_path, max_bytes=self.max_source_bytes)
        derived_document_id = document.document_id
        if document_id is not None and document_id != derived_document_id:
            raise ValueError("document_id does not match the source document")
        result, points = self._prepare_file(validated_path, document=document)
        self._store_replacement(derived_document_id, points)
        self._emit_ingest_event(result)
        return result

    def _validate_unrooted_source_size(self, path: Path) -> None:
        """Keep the size guard active for library callers without a source root."""

        if not path.is_file():
            raise ValueError("source path is not a file")
        if path.stat().st_size > self.max_source_bytes:
            raise ValueError("source file exceeds the configured size limit")

    def _store_replacement(
        self, document_id: str, points: list[models.PointStruct]
    ) -> None:
        replace_document = getattr(self.store, "replace_document", None)
        if replace_document is not None:
            replace_document(document_id, points)
        else:
            self.delete_document(document_id)
            self.store.upsert(points)

    def _point(self, document: object, chunk: Chunk, vector: list[float]) -> models.PointStruct:
        self._validate_vector(vector)
        payload = {
            "document_id": chunk.document_id,
            "chunk_id": chunk.chunk_id,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "heading_path": list(chunk.heading_path),
            "location": chunk.location,
            "token_count": chunk.token_count,
            "owner_id": "me",
            "document_status": "active",
            "embedding_manifest_id": self.provider.manifest.manifest_id,
            "chunking_version": chunk.chunking_version,
            "source_uri": document.source_uri,
            "source_type": document.source_type,
            "title": document.title,
            "content_hash": document.content_hash,
            "parser_version": document.parser_version,
        }
        security_flags = detect_prompt_injection(chunk.text)
        payload["security_flags"] = list(security_flags)
        if security_flags:
            payload["document_status"] = "needs_review"
            emit_audit_event(
                "document_quarantined",
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                security_flags=list(security_flags),
            )
        validate_schema(payload, "chunk-payload.schema.json")
        prepare_vector = getattr(self.store, "prepare_vector", None)
        stored_vector = prepare_vector(vector, chunk.text) if prepare_vector else vector
        return models.PointStruct(
            id=point_id_for_chunk(chunk.chunk_id), vector=stored_vector, payload=payload
        )

    def _validate_vector(self, vector: list[float]) -> None:
        expected = self.provider.manifest.dimension
        if len(vector) != expected:
            raise ValueError(f"embedding dimension {len(vector)} does not match {expected}")
        try:
            finite = all(isfinite(value) for value in vector)
            norm_squared = sum(value * value for value in vector)
        except (TypeError, ValueError):
            raise ValueError("embedding vector must contain numeric values") from None
        if not finite or norm_squared <= 0:
            raise ValueError("embedding vector must be finite and non-zero")
