"""Privacy-conscious local corpus inventory for fixture preparation."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from personal_vector_db.chunking import CHUNKING_VERSION, chunk_document
from personal_vector_db.parsers import SUPPORTED_SUFFIXES, parse_source
from personal_vector_db.security import is_excluded_directory, validate_source_path
from personal_vector_db.validation import validate_schema


def _size_bucket(size: int) -> str:
    if size < 10_000:
        return "small"
    if size < 1_000_000:
        return "medium"
    return "large"


def count_excluded_files(root: Path) -> int:
    """Count files under default excluded directories without exposing their paths."""

    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise ValueError("corpus root is not a directory")
    return sum(
        path.is_file() and is_excluded_directory(path, resolved_root)
        for path in resolved_root.rglob("*")
    )


def summarize_unsupported_files(root: Path) -> dict[str, int]:
    """Count non-excluded files skipped by the parser allowlist, without paths."""

    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise ValueError("corpus root is not a directory")
    suffixes: Counter[str] = Counter()
    for path in resolved_root.rglob("*"):
        if (
            path.is_file()
            and not is_excluded_directory(path, resolved_root)
            and path.suffix.lower() not in SUPPORTED_SUFFIXES
        ):
            suffixes[path.suffix.lower() or "<none>"] += 1
    return dict(sorted(suffixes.items()))


def inventory_sources(
    root: Path,
    *,
    max_source_bytes: int = 10_000_000,
    max_files: int = 5_000,
    max_total_bytes: int = 1_000_000_000,
) -> list[dict[str, object]]:
    """Summarize supported local sources without returning source text."""

    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise ValueError("corpus root is not a directory")
    if max_source_bytes < 1:
        raise ValueError("max_source_bytes must be positive")
    if isinstance(max_files, bool) or not isinstance(max_files, int) or max_files < 1:
        raise ValueError("max_files must be a positive integer")
    if (
        isinstance(max_total_bytes, bool)
        or not isinstance(max_total_bytes, int)
        or max_total_bytes < 1
    ):
        raise ValueError("max_total_bytes must be a positive integer")

    paths: list[Path] = []
    total_source_bytes = 0
    for path in resolved_root.rglob("*"):
        if (
            not path.is_file()
            or is_excluded_directory(path, resolved_root)
            or path.suffix.lower() not in SUPPORTED_SUFFIXES
        ):
            continue
        if len(paths) >= max_files:
            raise ValueError("corpus exceeds the configured source file limit")
        source_size = path.stat().st_size
        if total_source_bytes + source_size > max_total_bytes:
            raise ValueError("corpus exceeds the configured total source bytes limit")
        total_source_bytes += source_size
        paths.append(path)

    records: list[dict[str, object]] = []
    for path in sorted(paths):
        relative_path = path.relative_to(resolved_root).as_posix()
        record: dict[str, object] = {
            "relative_path": relative_path,
            "suffix": path.suffix.lower(),
            "byte_size": path.stat().st_size,
            "size_bucket": _size_bucket(path.stat().st_size),
            "content_hash": None,
        }
        try:
            validated_path = validate_source_path(
                path, resolved_root, max_bytes=max_source_bytes
            )
            raw = validated_path.read_bytes()
            record["content_hash"] = f"sha256:{hashlib.sha256(raw).hexdigest()}"
            document = parse_source(validated_path, max_bytes=max_source_bytes)
            chunks = chunk_document(document)
            extracted_char_count = sum(len(section.text) for section in document.sections)
            record.update(
                {
                    "document_id": document.document_id,
                    "source_type": document.source_type,
                    "parser_version": document.parser_version,
                    "section_count": len(document.sections),
                    "extracted_char_count": extracted_char_count,
                    "nonempty_section_count": sum(
                        bool(section.text.strip()) for section in document.sections
                    ),
                    "chunk_count": len(chunks),
                    "chunk_ids": [chunk.chunk_id for chunk in chunks],
                    "status": "parsed",
                    "extraction_status": "nonempty" if extracted_char_count else "empty",
                }
            )
        except Exception as error:
            record.update(
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "extraction_status": (
                        "empty"
                        if str(error).startswith("empty parsed document:")
                        else "not-available"
                    ),
                }
            )
        records.append(record)
    # Duplicate bytes are common in personal exports (backup folders, synced
    # copies, and renamed notes).  Surface them for review without merging or
    # deleting anything: paths may have different intended provenance even
    # when their raw bytes match.
    paths_by_hash: dict[str, list[str]] = {}
    for record in records:
        content_hash = record.get("content_hash")
        record["duplicate_of"] = None
        if not isinstance(content_hash, str):
            continue
        paths_by_hash.setdefault(content_hash, []).append(str(record["relative_path"]))
    for record in records:
        content_hash = record.get("content_hash")
        if not isinstance(content_hash, str):
            continue
        paths = paths_by_hash[content_hash]
        canonical_path = min(paths, key=lambda value: (value.count("/"), value))
        if canonical_path != record["relative_path"]:
            record["duplicate_of"] = canonical_path
    return records


def write_corpus_inventory(
    root: Path,
    output: Path,
    *,
    max_source_bytes: int = 10_000_000,
    max_files: int = 5_000,
    max_total_bytes: int = 1_000_000_000,
) -> list[dict[str, object]]:
    """Write deterministic inventory JSON; never include parsed source text."""

    records = inventory_sources(
        root,
        max_source_bytes=max_source_bytes,
        max_files=max_files,
        max_total_bytes=max_total_bytes,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return records


def read_corpus_manifest(path: Path) -> dict[str, object]:
    """Read a validated, text-free corpus manifest for backup provenance."""

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("corpus manifest could not be read") from error
    if not isinstance(manifest, dict):
        raise ValueError("corpus manifest must be an object")
    validate_schema(manifest, "corpus-manifest.schema.json")
    if len(manifest["chunk_ids"]) != manifest["total_chunks"]:
        raise ValueError("corpus manifest total_chunks does not match chunk_ids")
    return manifest


def write_corpus_manifest(
    root: Path, inventory: list[dict[str, object]], output: Path
) -> dict[str, object]:
    """Write a deterministic, text-free identity manifest for an inventory."""

    identity_rows = [
        {
            "relative_path": record["relative_path"],
            "content_hash": record["content_hash"],
            "status": record["status"],
        }
        for record in inventory
    ]
    canonical = json.dumps(identity_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    parsed = [record for record in inventory if record.get("status") == "parsed"]
    chunk_ids = [
        chunk_id
        for record in parsed
        for chunk_id in record.get("chunk_ids", [])
    ]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("inventory contains duplicate chunk_ids")
    if sum(int(record.get("chunk_count", 0)) for record in parsed) != len(chunk_ids):
        raise ValueError("inventory chunk_count does not match chunk_ids")
    chunk_size_buckets = {
        str(chunk_id): str(record["size_bucket"])
        for record in parsed
        for chunk_id in record.get("chunk_ids", [])
        if record.get("size_bucket") in {"small", "medium", "large"}
    }
    if len(chunk_size_buckets) != len(chunk_ids):
        raise ValueError("parsed chunks are missing a valid size bucket")
    manifest: dict[str, object] = {
        "schema_version": "corpus-manifest-v1",
        "root_name": root.resolve().name,
        "corpus_checksum": f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}",
        "source_count": len(inventory),
        "parsed_source_count": len(parsed),
        "failed_source_count": len(inventory) - len(parsed),
        "total_bytes": sum(int(record["byte_size"]) for record in inventory),
        "total_chunks": sum(int(record.get("chunk_count", 0)) for record in parsed),
        "total_extracted_chars": sum(
            int(record.get("extracted_char_count", 0)) for record in parsed
        ),
        "empty_extraction_count": sum(
            record.get("extraction_status") == "empty" for record in inventory
        ),
        "size_bucket_counts": dict(
            sorted(
                Counter(
                    str(record["size_bucket"])
                    for record in inventory
                    if record.get("size_bucket") in {"small", "medium", "large"}
                ).items()
            )
        ),
        "chunk_ids": sorted(chunk_ids),
        "chunk_size_buckets": dict(sorted(chunk_size_buckets.items())),
        "chunking_version": CHUNKING_VERSION,
        "parser_versions": sorted(
            {str(record["parser_version"]) for record in parsed if "parser_version" in record}
        ),
        "format_counts": dict(
            sorted(Counter(str(record["suffix"]) for record in inventory).items())
        ),
        "failure_types": dict(
            sorted(
                Counter(
                    str(record["error_type"])
                    for record in inventory
                    if record.get("status") == "failed" and record.get("error_type")
                ).items()
            )
        ),
        "duplicate_count": sum(1 for record in inventory if record.get("duplicate_of")),
        "privacy_classification": "private-local",
    }
    validate_schema(manifest, "corpus-manifest.schema.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
