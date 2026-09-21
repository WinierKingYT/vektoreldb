"""Privacy-safe final measurement readiness checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .benchmark import fixture_coverage_report, load_query_cases
from .corpus import summarize_corpus_inventory
from .validation import validate_schema


def _missing(path: Path) -> dict[str, object]:
    return {"status": "missing", "error_type": "FileNotFoundError"}


def _failed(error: Exception) -> dict[str, object]:
    return {"status": "failed", "error_type": type(error).__name__}


def build_final_readiness_report(
    *,
    inventory_path: Path,
    fixture_path: Path,
    fixture_manifest_path: Path,
    labels_path: Path | None = None,
    corpus_manifest_path: Path | None = None,
) -> dict[str, object]:
    """Summarize final gates without starting embeddings, Qdrant, or network calls."""

    report: dict[str, object] = {
        "schema_version": "final-readiness-report-v1",
        "privacy_classification": "private-local",
        "corpus": {"status": "missing"},
        "fixture": {"status": "missing"},
        "overall_status": "incomplete",
    }

    if not inventory_path.is_file():
        report["corpus"] = _missing(inventory_path)
    else:
        try:
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            quality = summarize_corpus_inventory(inventory)
            report["corpus"] = {
                "status": "ready",
                "source_count": quality["source_count"],
                "parsed_source_count": quality["parsed_source_count"],
                "failed_source_count": quality["failed_source_count"],
                "duplicate_count": quality["duplicate_count"],
                "total_chunks": quality["total_chunks"],
                "quality_schema_version": quality["schema_version"],
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            report["corpus"] = _failed(error)

    if not fixture_path.is_file() or not fixture_manifest_path.is_file():
        report["fixture"] = {
            "status": "missing",
            "missing_fixture": not fixture_path.is_file(),
            "missing_manifest": not fixture_manifest_path.is_file(),
        }
    else:
        try:
            cases = load_query_cases(fixture_path)
            coverage = fixture_coverage_report(
                cases,
                fixture_manifest_path,
                labels_path=labels_path if labels_path and labels_path.is_file() else None,
                corpus_manifest_path=(
                    corpus_manifest_path
                    if corpus_manifest_path and corpus_manifest_path.is_file()
                    else None
                ),
                fixture_checksum="sha256:" + hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
            )
            final_ready = bool(
                coverage["coverage_complete"]
                and coverage["manifest_status"] == "ready"
                and coverage["labels_status"] == "complete"
                and coverage["corpus_binding_status"] == "valid"
                and coverage["parser_versions_binding_status"] == "valid"
                and coverage["chunk_size_bucket_binding_status"] == "valid"
            )
            report["fixture"] = {
                "status": "ready" if final_ready else "incomplete",
                "query_count": coverage["query_count"],
                "minimum_query_count": coverage["minimum_query_count"],
                "coverage_complete": coverage["coverage_complete"],
                "labels_status": coverage["labels_status"],
                "manifest_status": coverage["manifest_status"],
                "corpus_binding_status": coverage["corpus_binding_status"],
                "parser_versions_binding_status": coverage["parser_versions_binding_status"],
                "chunk_size_bucket_binding_status": coverage[
                    "chunk_size_bucket_binding_status"
                ],
                "missing_document_size_buckets": coverage["missing_document_size_buckets"],
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            report["fixture"] = _failed(error)

    report["overall_status"] = (
        "ready"
        if report["corpus"].get("status") == "ready"
        and report["fixture"].get("status") == "ready"
        else "incomplete"
    )
    validate_schema(report, "final-readiness-report.schema.json")
    return report
