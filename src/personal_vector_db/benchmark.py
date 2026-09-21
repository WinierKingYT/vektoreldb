"""Small, reproducible retrieval benchmark primitives."""

import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from math import ceil, isfinite, log2
from pathlib import Path
from statistics import fmean
from time import perf_counter, process_time
from typing import Protocol

from personal_vector_db.retrieval import RetrievalFilter
from personal_vector_db.validation import validate_schema

MAX_CONCURRENCY_PROBE_REQUESTS = 100_000
MAX_CONCURRENCY_MATRIX_LEVELS = 16


@dataclass(frozen=True)
class QueryCase:
    query_id: str
    text: str
    relevant_chunk_ids: frozenset[str]
    query_type: str = "semantic"
    filters: RetrievalFilter | None = None
    split: str = "unspecified"
    size_bucket: str | None = None
    filter_selectivity: str | None = None


def _duplicate_query_counts(cases: Sequence[QueryCase]) -> tuple[int, int, int]:
    groups: dict[str, list[QueryCase]] = {}
    for case in cases:
        normalized_text = " ".join(case.text.casefold().split())
        groups.setdefault(normalized_text, []).append(case)
    duplicate_groups = sum(len(group) > 1 for group in groups.values())
    duplicate_count = sum(len(group) - 1 for group in groups.values() if len(group) > 1)
    cross_split_count = sum(
        len({case.split for case in group}) > 1
        for group in groups.values()
        if len(group) > 1
    )
    return duplicate_groups, duplicate_count, cross_split_count


@dataclass(frozen=True)
class AbstentionThresholdResult:
    """Privacy-safe validation summary for a candidate score threshold."""

    threshold: float
    positive_query_count: int
    negative_query_count: int
    positive_acceptance_rate: float
    negative_success_rate: float
    false_abstention_rate: float
    false_acceptance_rate: float

    def to_dict(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "positive_query_count": self.positive_query_count,
            "negative_query_count": self.negative_query_count,
            "positive_acceptance_rate": self.positive_acceptance_rate,
            "negative_success_rate": self.negative_success_rate,
            "false_abstention_rate": self.false_abstention_rate,
            "false_acceptance_rate": self.false_acceptance_rate,
        }


def evaluate_abstention_threshold(
    cases: Sequence[QueryCase],
    score_lists: Sequence[Sequence[float]],
    *,
    threshold: float,
) -> AbstentionThresholdResult:
    """Evaluate threshold acceptance using only query type and returned scores."""

    if not cases:
        raise ValueError("cases cannot be empty")
    if len(cases) != len(score_lists):
        raise ValueError("cases and score_lists must have the same length")
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not isfinite(threshold)
        or not -1.0 <= threshold <= 1.0
    ):
        raise ValueError("threshold must be between -1 and 1")

    accepted = []
    for scores in score_lists:
        numeric_scores = list(scores)
        if any(
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not isfinite(score)
            or not -1.0 <= score <= 1.0
            for score in numeric_scores
        ):
            raise ValueError("scores must be finite and between -1 and 1")
        accepted.append(bool(numeric_scores) and max(numeric_scores) >= threshold)

    positive = [
        accepted[index] for index, case in enumerate(cases) if case.query_type != "negative"
    ]
    negative = [
        accepted[index] for index, case in enumerate(cases) if case.query_type == "negative"
    ]
    positive_count = len(positive)
    negative_count = len(negative)
    positive_acceptance = sum(positive) / positive_count if positive_count else 0.0
    negative_success = (
        sum(not value for value in negative) / negative_count if negative_count else 0.0
    )
    return AbstentionThresholdResult(
        threshold=threshold,
        positive_query_count=positive_count,
        negative_query_count=negative_count,
        positive_acceptance_rate=round(positive_acceptance, 6),
        negative_success_rate=round(negative_success, 6),
        false_abstention_rate=round(1.0 - positive_acceptance, 6),
        false_acceptance_rate=round(1.0 - negative_success, 6),
    )


def choose_abstention_threshold(
    cases: Sequence[QueryCase],
    score_lists: Sequence[Sequence[float]],
    *,
    min_positive_acceptance: float = 0.9,
    min_negative_success: float = 0.8,
) -> AbstentionThresholdResult:
    """Choose the highest validation threshold satisfying both quality floors."""

    for value, name in (
        (min_positive_acceptance, "min_positive_acceptance"),
        (min_negative_success, "min_negative_success"),
    ):
        if not isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")
    if not cases:
        raise ValueError("cases cannot be empty")
    if len(cases) != len(score_lists):
        raise ValueError("cases and score_lists must have the same length")
    candidates = {1.0}
    for scores in score_lists:
        for score in scores:
            if not isfinite(score) or not -1.0 <= score <= 1.0:
                raise ValueError("scores must be finite and between -1 and 1")
            candidates.add(float(score))
    evaluations = [
        evaluate_abstention_threshold(cases, score_lists, threshold=threshold)
        for threshold in sorted(candidates, reverse=True)
    ]
    feasible = [
        result
        for result in evaluations
        if result.positive_acceptance_rate >= min_positive_acceptance
        and result.negative_success_rate >= min_negative_success
    ]
    if not feasible:
        raise ValueError("no abstention threshold satisfies the validation quality floors")
    return feasible[0]


QUERY_TYPES = frozenset(
    {"semantic", "exact_identifier", "typo", "morphology", "long_context", "negative"}
)
FIXTURE_SPLITS = frozenset({"development", "validation", "test", "unspecified"})
SIZE_BUCKETS = frozenset({"small", "medium", "large"})
SELECTIVITY_BUCKETS = frozenset({"low", "medium", "high"})


@dataclass(frozen=True)
class BenchmarkResult:
    query_count: int
    recall_at_k: float
    elapsed_seconds: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    error_rate: float
    mrr_at_k: float
    ndcg_at_k: float
    negative_success_rate: float = 0.0
    query_type_metrics: dict[str, dict[str, float | int]] = field(default_factory=dict)
    cpu_seconds: float = 0.0
    rss_mb: float | None = None
    fixture_checksum: str | None = None
    corpus_checksum: str | None = None
    embedding_manifest_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "query_count": self.query_count,
            "recall_at_k": self.recall_at_k,
            "elapsed_seconds": self.elapsed_seconds,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "error_rate": self.error_rate,
            "mrr_at_k": self.mrr_at_k,
            "ndcg_at_k": self.ndcg_at_k,
            "negative_success_rate": self.negative_success_rate,
            "query_type_metrics": self.query_type_metrics,
            "cpu_seconds": self.cpu_seconds,
            "rss_mb": self.rss_mb,
            "fixture_checksum": self.fixture_checksum,
            "corpus_checksum": self.corpus_checksum,
            "embedding_manifest_id": self.embedding_manifest_id,
        }


@dataclass(frozen=True)
class ConcurrencyResult:
    """Privacy-safe latency/throughput summary for concurrent search probes."""

    concurrency: int
    total_requests: int
    successful_requests: int
    error_count: int
    elapsed_seconds: float
    throughput_per_second: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    error_types: dict[str, int] = field(default_factory=dict)
    fixture_checksum: str | None = None
    corpus_checksum: str | None = None
    embedding_manifest_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "concurrency": self.concurrency,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "error_count": self.error_count,
            "elapsed_seconds": self.elapsed_seconds,
            "throughput_per_second": self.throughput_per_second,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "error_types": self.error_types,
            "fixture_checksum": self.fixture_checksum,
            "corpus_checksum": self.corpus_checksum,
            "embedding_manifest_id": self.embedding_manifest_id,
        }


def recall_regression_points(baseline: BenchmarkResult, candidate: BenchmarkResult) -> float:
    """Return candidate Recall@k loss in percentage points (negative means improvement)."""

    if baseline.query_count != candidate.query_count:
        raise ValueError("baseline and candidate must use the same query count")
    return (baseline.recall_at_k - candidate.recall_at_k) * 100


def assert_regression_within(
    baseline: BenchmarkResult, candidate: BenchmarkResult, *, max_points: float = 2.0
) -> None:
    """Raise when a candidate falls beyond the documented recall regression budget."""

    if max_points < 0:
        raise ValueError("max_points cannot be negative")
    regression = recall_regression_points(baseline, candidate)
    if regression > max_points:
        raise AssertionError(
            f"Recall@k regression {regression:.3f} points exceeds {max_points:.3f} point budget"
        )


def write_benchmark_result(path: Path, result: BenchmarkResult) -> None:
    validate_schema(result.to_dict(), "benchmark-result.schema.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")


def write_benchmark_results(path: Path, results: list[BenchmarkResult]) -> None:
    """Write raw repeated runs plus a privacy-safe aggregate summary."""

    if not results:
        raise ValueError("benchmark results cannot be empty")
    for result in results:
        validate_schema(result.to_dict(), "benchmark-result.schema.json")
    _ensure_provenance_consistency(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "runs": [result.to_dict() for result in results],
                "summary": summarize_benchmark_results(results),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def summarize_benchmark_results(results: Sequence[BenchmarkResult]) -> dict[str, object]:
    """Summarize repeated benchmark runs without including query or document text."""

    if not results:
        raise ValueError("benchmark results cannot be empty")
    _ensure_provenance_consistency(results)
    query_counts = {result.query_count for result in results}
    if len(query_counts) != 1:
        raise ValueError("benchmark runs must use the same query count")
    metric_names = (
        "recall_at_k",
        "mrr_at_k",
        "ndcg_at_k",
        "negative_success_rate",
        "latency_p50_ms",
        "latency_p95_ms",
        "latency_p99_ms",
        "error_rate",
        "elapsed_seconds",
        "cpu_seconds",
    )
    metrics: dict[str, dict[str, float | None]] = {}
    for name in metric_names:
        values = [float(getattr(result, name)) for result in results]
        metrics[name] = {
            "mean": round(fmean(values), 6),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
        }
    rss_values = [result.rss_mb for result in results if result.rss_mb is not None]
    metrics["rss_mb"] = (
        {
            "mean": round(fmean(rss_values), 6),
            "min": round(min(rss_values), 6),
            "max": round(max(rss_values), 6),
        }
        if rss_values
        else {"mean": None, "min": None, "max": None}
    )
    return {
        "run_count": len(results),
        "query_count": next(iter(query_counts)),
        "metrics": metrics,
    }


def _ensure_provenance_consistency(
    results: Sequence[BenchmarkResult | ConcurrencyResult],
) -> None:
    """Reject aggregates that combine runs from different input contracts."""

    for field_name in ("fixture_checksum", "corpus_checksum", "embedding_manifest_id"):
        values = {getattr(result, field_name) for result in results}
        if len(values) > 1:
            raise ValueError(f"benchmark runs must use the same {field_name}")


def load_query_cases(path: Path) -> list[QueryCase]:
    """Load the versioned benchmark fixture without accepting unknown fields."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("benchmark fixture must be a non-empty list")
    cases = []
    query_ids: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("benchmark case must be an object")
        allowed_fields = {
            "query_id",
            "text",
            "relevant_chunk_ids",
            "query_type",
            "filters",
            "split",
            "size_bucket",
            "filter_selectivity",
        }
        if not set(item).issubset(allowed_fields):
            raise ValueError("benchmark case has an invalid shape")
        query_id = item["query_id"]
        text = item["text"]
        relevant_chunk_ids = item["relevant_chunk_ids"]
        if (
            not isinstance(query_id, str)
            or not query_id.strip()
            or query_id in query_ids
        ):
            raise ValueError("benchmark case has a missing or duplicate query_id")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("benchmark case text must be a non-empty string")
        if not isinstance(relevant_chunk_ids, list) or not all(
            isinstance(chunk_id, str) and chunk_id.strip()
            for chunk_id in relevant_chunk_ids
        ):
            raise ValueError("relevant_chunk_ids must be a list of non-empty strings")
        query_type = item.get("query_type", "semantic")
        if query_type not in QUERY_TYPES:
            raise ValueError("benchmark case has an invalid query_type")
        if query_type == "negative" and relevant_chunk_ids:
            raise ValueError("negative benchmark cases cannot have relevant chunks")
        split = item.get("split", "unspecified")
        if split not in FIXTURE_SPLITS:
            raise ValueError("benchmark case has an invalid split")
        size_bucket = item.get("size_bucket")
        if size_bucket is not None and size_bucket not in SIZE_BUCKETS:
            raise ValueError("benchmark case has an invalid size_bucket")
        filter_selectivity = item.get("filter_selectivity")
        if filter_selectivity is not None and filter_selectivity not in SELECTIVITY_BUCKETS:
            raise ValueError("benchmark case has an invalid filter_selectivity")
        raw_filters = item.get("filters")
        filters = None
        if raw_filters is not None:
            if not isinstance(raw_filters, dict) or not set(raw_filters).issubset(
                {"document_ids", "source_uris", "source_types", "titles"}
            ):
                raise ValueError("benchmark filters have an invalid shape")
            if any(
                not isinstance(values, list)
                or not all(isinstance(value, str) and value.strip() for value in values)
                for values in raw_filters.values()
            ):
                raise ValueError("benchmark filter values must be non-empty strings")
            filters = RetrievalFilter(
                document_ids=tuple(raw_filters.get("document_ids", [])),
                source_uris=tuple(raw_filters.get("source_uris", [])),
                source_types=tuple(raw_filters.get("source_types", [])),
                titles=tuple(raw_filters.get("titles", [])),
            )
        query_ids.add(query_id)
        cases.append(
            QueryCase(
                query_id=query_id,
                text=text,
                relevant_chunk_ids=frozenset(relevant_chunk_ids),
                query_type=query_type,
                filters=filters,
                split=split,
                size_bucket=size_bucket,
                filter_selectivity=filter_selectivity,
            )
        )
    return cases


def _query_case_to_dict(case: QueryCase) -> dict[str, object]:
    """Serialize a validated query case without adding provenance or source text."""

    encoded: dict[str, object] = {
        "query_id": case.query_id,
        "text": case.text,
        "relevant_chunk_ids": sorted(case.relevant_chunk_ids),
        "query_type": case.query_type,
        "split": case.split,
    }
    if case.filters is not None:
        encoded["filters"] = {
            key: list(values)
            for key, values in {
                "document_ids": case.filters.document_ids,
                "source_uris": case.filters.source_uris,
                "source_types": case.filters.source_types,
                "titles": case.filters.titles,
            }.items()
            if values
        }
    if case.size_bucket is not None:
        encoded["size_bucket"] = case.size_bucket
    if case.filter_selectivity is not None:
        encoded["filter_selectivity"] = case.filter_selectivity
    return encoded


def merge_query_fixture_files(paths: Sequence[Path], output: Path) -> dict[str, int]:
    """Merge validated query shards while rejecting ID and normalized-text collisions."""

    if not paths:
        raise ValueError("at least one query fixture shard is required")
    cases: list[QueryCase] = []
    seen_ids: set[str] = set()
    seen_texts: set[str] = set()
    for path in paths:
        for case in load_query_cases(path):
            normalized_text = " ".join(case.text.casefold().split())
            if case.query_id in seen_ids:
                raise ValueError("query fixture shards contain duplicate query_id")
            if normalized_text in seen_texts:
                raise ValueError("query fixture shards contain duplicate normalized query")
            seen_ids.add(case.query_id)
            seen_texts.add(normalized_text)
            cases.append(case)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps([_query_case_to_dict(case) for case in cases], ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return {"shard_count": len(paths), "query_count": len(cases)}


def merge_query_label_files(paths: Sequence[Path], output: Path) -> dict[str, int]:
    """Merge validated label shards without allowing duplicate query annotations."""

    if not paths:
        raise ValueError("at least one query label shard is required")
    labels: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    expected_provenance: tuple[object, ...] | None = None
    for path in paths:
        shard = load_query_labels(path)
        for query_id, label in shard.items():
            if query_id in seen_ids:
                raise ValueError("query label shards contain duplicate query_id")
            provenance = (
                label["corpus_checksum"],
                label["parser_version"],
                label["chunking_version"],
                tuple(sorted(label.get("parser_versions", ()))),
            )
            if expected_provenance is None:
                expected_provenance = provenance
            elif provenance != expected_provenance:
                raise ValueError("query label shards have incompatible provenance")
            seen_ids.add(query_id)
            labels.append(label)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"shard_count": len(paths), "label_count": len(labels)}


def load_query_labels(path: Path) -> dict[str, dict[str, object]]:
    """Load strict annotation records while keeping source text out of labels."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("query labels must be a non-empty list")
    validate_schema(raw, "query-labels.schema.json")
    labels: dict[str, dict[str, object]] = {}
    for label in raw:
        query_id = str(label["query_id"])
        if query_id in labels:
            raise ValueError("query labels contain duplicate query_id")
        labels[query_id] = label
    return labels


def write_query_label_template(
    path: Path,
    cases: list[QueryCase],
    *,
    corpus_manifest_path: Path | None = None,
) -> None:
    """Write a review-required label skeleton without copying source text."""

    if not cases:
        raise ValueError("fixture cases cannot be empty")
    provenance = {
        "corpus_checksum": "REPLACE_WITH_CORPUS_SHA256",
        "parser_version": "REPLACE_WITH_PARSER_VERSION",
        "chunking_version": "REPLACE_WITH_CHUNKING_VERSION",
    }
    if corpus_manifest_path is not None:
        raw_manifest = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
        if not isinstance(raw_manifest, dict):
            raise ValueError("corpus manifest must be an object")
        validate_schema(raw_manifest, "corpus-manifest.schema.json")
        checksum = raw_manifest.get("corpus_checksum")
        chunking_version = raw_manifest.get("chunking_version")
        parser_versions = raw_manifest.get("parser_versions")
        if not isinstance(checksum, str) or not checksum.strip():
            raise ValueError("corpus manifest is missing corpus_checksum")
        if not isinstance(chunking_version, str) or not chunking_version.strip():
            raise ValueError("corpus manifest is missing chunking_version")
        if not isinstance(parser_versions, list) or not parser_versions:
            raise ValueError("corpus manifest is missing parser_versions")
        provenance["corpus_checksum"] = checksum
        provenance["chunking_version"] = chunking_version
        normalized_parser_versions = sorted(
            version for version in parser_versions if isinstance(version, str)
        )
        if len(normalized_parser_versions) != len(parser_versions):
            raise ValueError("corpus manifest parser_versions must contain strings")
        provenance["parser_versions"] = normalized_parser_versions
        provenance["parser_version"] = (
            normalized_parser_versions[0]
            if len(normalized_parser_versions) == 1
            else "mixed"
        )
        known_chunk_ids = set(raw_manifest["chunk_ids"])
        if any(
            set(case.relevant_chunk_ids) - known_chunk_ids
            for case in cases
        ):
            raise ValueError("fixture contains chunk references outside the corpus manifest")

    labels = [
        {
            "query_id": case.query_id,
            "relevant_chunk_ids": sorted(case.relevant_chunk_ids),
            "annotator": "REPLACE_WITH_ANNOTATOR",
            "annotated_at": "REPLACE_WITH_ISO8601_TIMESTAMP",
            "source": "derived",
            "decision_note": (
                "REVIEW_REQUIRED: verify relevant_chunk_ids against the current corpus"
            ),
            **provenance,
        }
        for case in cases
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def fixture_coverage_report(
    cases: list[QueryCase],
    manifest_path: Path,
    labels_path: Path | None = None,
    corpus_manifest_path: Path | None = None,
    fixture_checksum: str | None = None,
) -> dict[str, object]:
    """Return privacy-safe fixture readiness counts without enforcing final gates."""

    if not cases:
        raise ValueError("fixture cases cannot be empty")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("fixture manifest must be an object")
    validate_schema(manifest, "query-fixture-manifest.schema.json")

    type_counts = Counter(case.query_type for case in cases)
    split_counts = Counter(case.split for case in cases)
    size_counts = Counter(case.size_bucket for case in cases if case.size_bucket is not None)
    selectivity_counts = Counter(
        case.filter_selectivity
        for case in cases
        if case.filter_selectivity is not None
    )
    (
        duplicate_query_group_count,
        duplicate_query_count,
        cross_split_duplicate_count,
    ) = _duplicate_query_counts(cases)
    corpus_binding_status = "not-provided"
    corpus_checksum_status = "not-provided"
    corpus_size_bucket_counts: dict[str, int] | None = None
    corpus_parser_versions: list[str] | None = None
    parser_versions_binding_status = "not-provided"
    corpus_checksum: str | None = None
    fixture_corpus_checksum = (
        manifest.get("corpus_checksum")
        if isinstance(manifest.get("corpus_checksum"), str)
        else None
    )
    fixture_parser_versions = (
        sorted(str(version) for version in manifest["parser_versions"])
        if isinstance(manifest.get("parser_versions"), list)
        else None
    )
    chunk_size_bucket_binding_status = "not-provided"
    queries_with_size_bucket_mismatch = 0
    unknown_size_bucket_chunk_count = 0
    known_chunk_ids: set[str] | None = None
    unknown_relevant_chunk_count = 0
    queries_with_unknown_relevant_chunks = 0
    label_provenance_status = "not-provided"
    label_provenance_mismatch_count = 0
    if corpus_manifest_path is not None:
        corpus_manifest = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
        if not isinstance(corpus_manifest, dict):
            raise ValueError("corpus manifest must be an object")
        validate_schema(corpus_manifest, "corpus-manifest.schema.json")
        corpus_checksum = str(corpus_manifest["corpus_checksum"])
        corpus_parser_versions = sorted(
            str(version) for version in corpus_manifest["parser_versions"]
        )
        parser_versions_binding_status = (
            "not-declared"
            if fixture_parser_versions is None
            else (
                "valid"
                if fixture_parser_versions == corpus_parser_versions
                else "mismatch"
            )
        )
        raw_size_bucket_counts = corpus_manifest.get("size_bucket_counts")
        if isinstance(raw_size_bucket_counts, dict):
            corpus_size_bucket_counts = {
                bucket: int(raw_size_bucket_counts.get(bucket, 0))
                for bucket in ("small", "medium", "large")
            }
        raw_chunk_size_buckets = corpus_manifest.get("chunk_size_buckets")
        if isinstance(raw_chunk_size_buckets, dict):
            chunk_size_buckets = {
                str(chunk_id): str(bucket)
                for chunk_id, bucket in raw_chunk_size_buckets.items()
            }
            chunk_size_bucket_binding_status = "valid"
        else:
            chunk_size_buckets = {}
            chunk_size_bucket_binding_status = "not-available"
        known_chunk_ids = set(corpus_manifest["chunk_ids"])
        if chunk_size_bucket_binding_status == "valid":
            unknown_size_bucket_chunk_count = len(known_chunk_ids - set(chunk_size_buckets))
            if unknown_size_bucket_chunk_count:
                chunk_size_bucket_binding_status = "mismatch"
        declared_checksum = manifest.get("corpus_checksum")
        corpus_checksum_status = (
            "not-declared"
            if declared_checksum in (None, "")
            else (
                "valid"
                if declared_checksum == corpus_manifest["corpus_checksum"]
                else "mismatch"
            )
        )
        unknown_by_case = [
            set(case.relevant_chunk_ids) - known_chunk_ids
            for case in cases
        ]
        unknown_relevant_chunk_count = sum(len(values) for values in unknown_by_case)
        queries_with_unknown_relevant_chunks = sum(bool(values) for values in unknown_by_case)
        if chunk_size_bucket_binding_status == "valid":
            for case in cases:
                if not case.relevant_chunk_ids or case.size_bucket is None:
                    continue
                buckets = {
                    chunk_size_buckets[chunk_id]
                    for chunk_id in case.relevant_chunk_ids
                    if chunk_id in chunk_size_buckets
                }
                unknown_size_bucket_chunk_count += len(
                    set(case.relevant_chunk_ids) - set(chunk_size_buckets)
                )
                if buckets and case.size_bucket not in buckets:
                    queries_with_size_bucket_mismatch += 1
            if queries_with_size_bucket_mismatch:
                chunk_size_bucket_binding_status = "mismatch"
        corpus_binding_status = (
            "mismatch"
            if (
                unknown_relevant_chunk_count
                or corpus_checksum_status == "mismatch"
                or parser_versions_binding_status == "mismatch"
                or chunk_size_bucket_binding_status == "mismatch"
            )
            else "valid"
        )
    required_types = [str(value) for value in manifest["required_query_types"]]
    required_sizes = [str(value) for value in manifest["required_document_size_buckets"]]
    required_selectivity = [
        str(value) for value in manifest["required_filter_selectivity_buckets"]
    ]
    minimum_per_type = int(manifest["minimum_queries_per_type"])
    recommended_split = manifest["recommended_split"]
    split_ratios = {
        split: round(count / len(cases), 6) for split, count in sorted(split_counts.items())
    }
    missing_splits = sorted(set(recommended_split) - set(split_counts))
    split_ratio_issues = [
        split
        for split, expected_ratio in recommended_split.items()
        if split in split_counts
        and abs(split_ratios[split] - expected_ratio) > manifest["split_tolerance"]
    ]
    missing_types = [
        query_type
        for query_type in required_types
        if type_counts.get(query_type, 0) < minimum_per_type
    ]
    missing_sizes = [
        bucket for bucket in required_sizes if size_counts.get(bucket, 0) == 0
    ]
    missing_selectivity = [
        bucket
        for bucket in required_selectivity
        if selectivity_counts.get(bucket, 0) == 0
    ]
    if labels_path is None:
        label_report: dict[str, object] = {
            "labels_status": "not-provided",
            "label_count": 0,
            "unlabeled_query_count": len(cases),
            "orphan_label_count": 0,
            "derived_label_count": 0,
            "review_required_label_count": 0,
        }
    else:
        labels = load_query_labels(labels_path)
        case_ids = {case.query_id for case in cases}
        label_ids = set(labels)
        provenance_fields = ("corpus_checksum", "parser_version", "chunking_version")
        declared_provenance_fields = tuple(
            field
            for field in provenance_fields
            if manifest.get(field) not in (None, "")
        )
        for label in labels.values():
            parser_versions_mismatch = (
                "parser_versions" in manifest
                and sorted(label.get("parser_versions", []))
                != sorted(manifest["parser_versions"])
            )
            if (
                any(label[field] != manifest[field] for field in declared_provenance_fields)
                or parser_versions_mismatch
            ):
                label_provenance_mismatch_count += 1
        if not declared_provenance_fields and "parser_versions" not in manifest:
            label_provenance_status = "not-declared"
        else:
            label_provenance_status = (
                "mismatch" if label_provenance_mismatch_count else "valid"
            )
        unknown_labeled_chunk_count = (
            sum(
                len(set(label["relevant_chunk_ids"]) - known_chunk_ids)
                for label in labels.values()
            )
            if known_chunk_ids is not None
            else 0
        )
        labels_with_unknown_chunks = (
            sum(
                bool(set(label["relevant_chunk_ids"]) - known_chunk_ids)
                for label in labels.values()
            )
            if known_chunk_ids is not None
            else 0
        )
        derived_count = sum(label["source"] == "derived" for label in labels.values())
        if label_ids != case_ids:
            labels_status = "incomplete"
        elif derived_count:
            labels_status = "review-required"
        else:
            labels_status = "complete"
        label_report = {
            "labels_status": labels_status,
            "label_provenance_status": label_provenance_status,
            "label_provenance_mismatch_count": label_provenance_mismatch_count,
            "label_count": len(labels),
            "unlabeled_query_count": len(case_ids - label_ids),
            "orphan_label_count": len(label_ids - case_ids),
            "derived_label_count": derived_count,
            "review_required_label_count": derived_count,
            "unknown_labeled_chunk_count": unknown_labeled_chunk_count,
            "labels_with_unknown_chunks": labels_with_unknown_chunks,
        }
        if unknown_labeled_chunk_count or label_provenance_mismatch_count:
            label_report["labels_status"] = "incomplete"
            if corpus_binding_status != "not-provided":
                corpus_binding_status = "mismatch"
    if labels_path is None:
        label_report["label_provenance_status"] = "not-provided"
        label_report["label_provenance_mismatch_count"] = 0
        label_report["unknown_labeled_chunk_count"] = 0
        label_report["labels_with_unknown_chunks"] = 0
    return {
        "manifest_status": manifest["status"],
        "query_count": len(cases),
        "minimum_query_count": manifest["minimum_query_count"],
        "query_type_counts": {
            query_type: type_counts.get(query_type, 0) for query_type in required_types
        },
        "missing_query_types": missing_types,
        "split_counts": dict(sorted(split_counts.items())),
        "split_ratios": split_ratios,
        "recommended_split": recommended_split,
        "missing_splits": missing_splits,
        "split_ratio_issues": split_ratio_issues,
        "size_bucket_counts": {
            bucket: size_counts.get(bucket, 0) for bucket in required_sizes
        },
        "corpus_size_bucket_counts": corpus_size_bucket_counts,
        "corpus_parser_versions": corpus_parser_versions,
        "fixture_parser_versions": fixture_parser_versions,
        "parser_versions_binding_status": parser_versions_binding_status,
        "corpus_checksum": corpus_checksum,
        "fixture_corpus_checksum": fixture_corpus_checksum,
        "fixture_checksum": fixture_checksum,
        "chunk_size_bucket_binding_status": chunk_size_bucket_binding_status,
        "queries_with_size_bucket_mismatch": queries_with_size_bucket_mismatch,
        "unknown_size_bucket_chunk_count": unknown_size_bucket_chunk_count,
        "missing_document_size_buckets": missing_sizes,
        "filter_selectivity_counts": {
            bucket: selectivity_counts.get(bucket, 0) for bucket in required_selectivity
        },
        "missing_filter_selectivity_buckets": missing_selectivity,
        "coverage_complete": bool(
            len(cases) >= int(manifest["minimum_query_count"])
            and not missing_types
            and not missing_sizes
            and not missing_selectivity
            and not missing_splits
            and not split_ratio_issues
            and "unspecified" not in split_counts
            and corpus_binding_status != "mismatch"
            and (
                corpus_manifest_path is None
                or (
                    corpus_checksum_status == "valid"
                    and parser_versions_binding_status == "valid"
                )
            )
            and cross_split_duplicate_count == 0
        ),
        "corpus_binding_status": corpus_binding_status,
        "corpus_checksum_status": corpus_checksum_status,
        "unknown_relevant_chunk_count": unknown_relevant_chunk_count,
        "queries_with_unknown_relevant_chunks": queries_with_unknown_relevant_chunks,
        "duplicate_query_group_count": duplicate_query_group_count,
        "duplicate_query_count": duplicate_query_count,
        "cross_split_duplicate_count": cross_split_duplicate_count,
        **label_report,
    }


def write_fixture_coverage_report(path: Path, report: dict[str, object]) -> None:
    """Write a schema-validated, privacy-safe fixture coverage report."""

    validate_schema(report, "fixture-coverage-report.schema.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def validate_fixture_requirements(
    cases: list[QueryCase],
    manifest_path: Path,
    corpus_manifest_path: Path | None = None,
    labels_path: Path | None = None,
) -> dict[str, object]:
    """Validate a labeled fixture against its explicit 300+ manifest contract."""

    if not cases:
        raise ValueError("fixture cases cannot be empty")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("fixture manifest must be an object")
    validate_schema(manifest, "query-fixture-manifest.schema.json")
    if corpus_manifest_path is not None:
        corpus_manifest = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
        if not isinstance(corpus_manifest, dict):
            raise ValueError("corpus manifest must be an object")
        validate_schema(corpus_manifest, "corpus-manifest.schema.json")
        manifest_chunk_ids = corpus_manifest["chunk_ids"]
        if len(manifest_chunk_ids) != corpus_manifest["total_chunks"]:
            raise ValueError("corpus manifest total_chunks does not match chunk_ids")
        fixture_checksum = manifest.get("corpus_checksum")
        corpus_checksum = corpus_manifest.get("corpus_checksum")
        if not isinstance(fixture_checksum, str) or not fixture_checksum:
            raise ValueError("fixture corpus_checksum is required for corpus binding")
        if fixture_checksum != corpus_checksum:
            raise ValueError("fixture corpus_checksum does not match corpus manifest")
        parser_version = manifest.get("parser_version")
        parser_versions = sorted(corpus_manifest.get("parser_versions", []))
        declared_parser_versions = manifest.get("parser_versions")
        if declared_parser_versions is not None:
            if sorted(declared_parser_versions) != parser_versions:
                raise ValueError("fixture parser_versions do not match corpus manifest")
            expected_parser_version = (
                parser_versions[0] if len(parser_versions) == 1 else "mixed"
            )
            if parser_version != expected_parser_version:
                raise ValueError("fixture parser_version summary does not match corpus manifest")
        elif parser_version not in parser_versions:
            raise ValueError("fixture parser_version is not present in corpus manifest")
        if manifest.get("chunking_version") != corpus_manifest.get("chunking_version"):
            raise ValueError("fixture chunking_version does not match corpus manifest")
        corpus_chunk_ids = set(corpus_manifest.get("chunk_ids", []))
        for case in cases:
            unknown_chunk_ids = set(case.relevant_chunk_ids) - corpus_chunk_ids
            if unknown_chunk_ids:
                raise ValueError(
                    f"fixture references unknown chunk_ids for {case.query_id}: "
                    + ", ".join(sorted(unknown_chunk_ids))
                )
    if labels_path is not None:
        labels = load_query_labels(labels_path)
        case_by_id = {case.query_id: case for case in cases}
        if set(labels) != set(case_by_id):
            raise ValueError("query labels must match fixture query_ids exactly")
        for query_id, label in labels.items():
            case = case_by_id[query_id]
            if manifest.get("status") == "ready" and label["source"] == "derived":
                raise ValueError(f"derived query label requires review for {query_id}")
            if set(label["relevant_chunk_ids"]) != set(case.relevant_chunk_ids):
                raise ValueError(f"query label relevance differs for {query_id}")
            for provenance_field in ("corpus_checksum", "parser_version", "chunking_version"):
                if label[provenance_field] != manifest[provenance_field]:
                    raise ValueError(f"query label {provenance_field} differs for {query_id}")
            if "parser_versions" in manifest:
                if label.get("parser_versions") != manifest["parser_versions"]:
                    raise ValueError(f"query label parser_versions differs for {query_id}")
    else:
        labels = None
    if manifest.get("status") != "ready":
        raise ValueError("fixture manifest is not ready for acceptance validation")
    minimum_count = manifest.get("minimum_query_count")
    minimum_per_type = manifest.get("minimum_queries_per_type")
    required_types = manifest.get("required_query_types")
    recommended_split = manifest.get("recommended_split")
    split_tolerance = manifest.get("split_tolerance", 0.05)
    if (
        not isinstance(minimum_count, int)
        or not isinstance(minimum_per_type, int)
        or not isinstance(required_types, list)
        or not all(isinstance(value, str) for value in required_types)
        or not isinstance(recommended_split, dict)
        or not all(isinstance(value, (int, float)) for value in recommended_split.values())
        or not isinstance(split_tolerance, (int, float))
        or not 0 <= split_tolerance < 1
    ):
        raise ValueError("fixture manifest has an invalid query requirement")
    if not recommended_split or abs(sum(recommended_split.values()) - 1.0) > 0.001:
        raise ValueError("fixture manifest split ratios must sum to 1")
    if any(value <= 0 for value in recommended_split.values()):
        raise ValueError("fixture manifest split ratios must be positive")
    for provenance_field in (
        "corpus_checksum",
        "parser_version",
        "chunking_version",
        "embedding_manifest_id",
    ):
        if not isinstance(manifest.get(provenance_field), str) or not manifest[provenance_field]:
            raise ValueError(f"fixture manifest is missing {provenance_field}")
    type_counts = {query_type: 0 for query_type in required_types}
    split_counts: dict[str, int] = {}
    size_counts: dict[str, int] = {}
    selectivity_counts: dict[str, int] = {}
    for case in cases:
        if case.query_type in type_counts:
            type_counts[case.query_type] += 1
        split_counts[case.split] = split_counts.get(case.split, 0) + 1
        if case.size_bucket is not None:
            size_counts[case.size_bucket] = size_counts.get(case.size_bucket, 0) + 1
        if case.filter_selectivity is not None:
            selectivity_counts[case.filter_selectivity] = (
                selectivity_counts.get(case.filter_selectivity, 0) + 1
            )
    _, duplicate_query_count, cross_split_duplicate_count = _duplicate_query_counts(cases)
    if cross_split_duplicate_count:
        raise ValueError("fixture contains cross-split duplicate queries")
    if duplicate_query_count:
        raise ValueError("fixture contains duplicate normalized queries")
    if len(cases) < minimum_count:
        raise ValueError(f"fixture needs at least {minimum_count} queries")
    if any(case.split == "unspecified" for case in cases):
        raise ValueError("fixture cases must declare a development, validation or test split")
    required_splits = set(recommended_split)
    missing_splits = sorted(required_splits - set(split_counts))
    if missing_splits:
        raise ValueError(f"fixture is missing required splits: {', '.join(missing_splits)}")
    for split, expected_ratio in recommended_split.items():
        actual_ratio = split_counts.get(split, 0) / len(cases)
        if abs(actual_ratio - expected_ratio) > split_tolerance:
            raise ValueError(
                f"fixture split {split} ratio {actual_ratio:.3f} is outside "
                f"tolerance {split_tolerance:.3f} of {expected_ratio:.3f}"
            )
    missing_types = [key for key, count in type_counts.items() if count < minimum_per_type]
    if missing_types:
        raise ValueError(f"fixture is missing required query types: {', '.join(missing_types)}")
    for bucket in manifest.get("required_document_size_buckets", []):
        if size_counts.get(bucket, 0) == 0:
            raise ValueError(f"fixture is missing document size bucket: {bucket}")
    for bucket in manifest.get("required_filter_selectivity_buckets", []):
        if selectivity_counts.get(bucket, 0) == 0:
            raise ValueError(f"fixture is missing filter selectivity bucket: {bucket}")
    return {
        "query_count": len(cases),
        "query_type_counts": type_counts,
        "split_counts": split_counts,
        "size_bucket_counts": size_counts,
        "filter_selectivity_counts": selectivity_counts,
        "label_count": len(labels) if labels is not None else 0,
    }


class Searcher(Protocol):
    def search(
        self, query: str, *, limit: int = 8, filters: RetrievalFilter | None = None
    ) -> list[object]: ...


def _search(searcher: Searcher, case: QueryCase, *, limit: int) -> list[object]:
    if case.filters is None or not case.filters.as_mapping():
        return searcher.search(case.text, limit=limit)
    return searcher.search(case.text, limit=limit, filters=case.filters)


def recall_at_k(cases: list[QueryCase], searcher: Searcher, *, k: int = 8) -> float:
    if not cases or not 1 <= k <= 100:
        raise ValueError("cases cannot be empty and k must be between 1 and 100")
    hits = 0
    positive_count = 0
    for case in cases:
        results = _search(searcher, case, limit=k)
        if case.query_type == "negative":
            continue
        positive_count += 1
        returned_ids = {result.chunk_id for result in results}
        hits += bool(returned_ids & case.relevant_chunk_ids)
    return hits / positive_count if positive_count else 0.0


def _rank_metrics(results: list[object], relevant: frozenset[str], k: int) -> tuple[float, float]:
    ranked_ids = [result.chunk_id for result in results[:k]]
    first_relevant = next(
        (rank for rank, chunk_id in enumerate(ranked_ids, start=1) if chunk_id in relevant),
        None,
    )
    reciprocal_rank = 0.0 if first_relevant is None else 1 / first_relevant
    dcg = sum(
        1 / log2(rank + 1)
        for rank, chunk_id in enumerate(ranked_ids, start=1)
        if chunk_id in relevant
    )
    ideal_relevant = min(len(relevant), k)
    ideal_dcg = sum(1 / log2(rank + 1) for rank in range(1, ideal_relevant + 1))
    return reciprocal_rank, (dcg / ideal_dcg if ideal_dcg else 0.0)


def _current_rss_bytes() -> int | None:
    """Return the benchmark process RSS using platform-native stdlib paths."""

    try:
        if sys.platform == "win32":
            import ctypes

            class ProcessMemoryCounters(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            process = ctypes.windll.kernel32.GetCurrentProcess()
            get_info = ctypes.windll.psapi.GetProcessMemoryInfo
            get_info.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ProcessMemoryCounters),
                ctypes.c_ulong,
            ]
            get_info.restype = ctypes.c_bool
            if get_info(process, ctypes.byref(counters), counters.cb):
                return int(counters.WorkingSetSize)
            return None
        status = "/proc/self/status"
        with open(status, encoding="utf-8") as stream:
            match = re.search(r"^VmRSS:\s+(\d+)\s+kB$", stream.read(), re.MULTILINE)
        return int(match.group(1)) * 1024 if match else None
    except (OSError, AttributeError, TypeError, ValueError):
        return None


def run_benchmark(
    cases: list[QueryCase],
    searcher: Searcher,
    *,
    k: int = 8,
    warmup: bool = True,
    fixture_checksum: str | None = None,
    corpus_checksum: str | None = None,
    embedding_manifest_id: str | None = None,
) -> BenchmarkResult:
    if not cases or not 1 <= k <= 100:
        raise ValueError("cases cannot be empty and k must be between 1 and 100")
    if warmup:
        try:
            _search(searcher, cases[0], limit=1)
        except Exception:
            # Warm-up is best effort; the measured loop must report the error.
            pass
    started = perf_counter()
    cpu_started = process_time()
    rss_before = _current_rss_bytes()
    latencies: list[float] = []
    hits = 0
    positive_count = 0
    errors = 0
    negative_count = 0
    negative_successes = 0
    reciprocal_ranks = []
    ndcgs = []
    type_stats: dict[str, dict[str, float]] = {}
    for case in cases:
        stats = type_stats.setdefault(
            case.query_type,
            {
                "count": 0,
                "errors": 0,
                "positives": 0,
                "hits": 0,
                "rr_sum": 0,
                "ndcg_sum": 0,
                "negative_successes": 0,
            },
        )
        stats["count"] += 1
        query_started = perf_counter()
        try:
            results = _search(searcher, case, limit=k)
            returned_ids = {result.chunk_id for result in results}
            if case.query_type == "negative":
                negative_count += 1
                negative_successes += not results
                stats["negative_successes"] += not results
            else:
                positive_count += 1
                hits += bool(returned_ids & case.relevant_chunk_ids)
                reciprocal_rank, ndcg = _rank_metrics(results, case.relevant_chunk_ids, k)
                reciprocal_ranks.append(reciprocal_rank)
                ndcgs.append(ndcg)
                stats["positives"] += 1
                stats["hits"] += bool(returned_ids & case.relevant_chunk_ids)
                stats["rr_sum"] += reciprocal_rank
                stats["ndcg_sum"] += ndcg
        except Exception:
            errors += 1
            stats["errors"] += 1
            if case.query_type == "negative":
                negative_count += 1
            else:
                positive_count += 1
                reciprocal_ranks.append(0.0)
                ndcgs.append(0.0)
                stats["positives"] += 1
        finally:
            latencies.append((perf_counter() - query_started) * 1000)

    def percentile(percent: float) -> float:
        ordered = sorted(latencies)
        index = max(0, min(len(ordered) - 1, ceil((percent / 100) * len(ordered)) - 1))
        return ordered[index]

    query_type_metrics = {}
    for query_type, stats in type_stats.items():
        positives = stats["positives"]
        negatives = stats["count"] - positives
        query_type_metrics[query_type] = {
            "count": int(stats["count"]),
            "error_rate": stats["errors"] / stats["count"] if stats["count"] else 0.0,
            "recall_at_k": stats["hits"] / positives if positives else 0.0,
            "mrr_at_k": stats["rr_sum"] / positives if positives else 0.0,
            "ndcg_at_k": stats["ndcg_sum"] / positives if positives else 0.0,
            "negative_success_rate": (
                stats["negative_successes"] / negatives if negatives else 0.0
            ),
        }
    rss_after = _current_rss_bytes()
    rss_samples = [value for value in (rss_before, rss_after) if value is not None]
    return BenchmarkResult(
        query_count=len(cases),
        recall_at_k=hits / positive_count if positive_count else 0.0,
        elapsed_seconds=perf_counter() - started,
        latency_p50_ms=percentile(50),
        latency_p95_ms=percentile(95),
        latency_p99_ms=percentile(99),
        error_rate=errors / len(cases),
        mrr_at_k=sum(reciprocal_ranks) / positive_count if positive_count else 0.0,
        ndcg_at_k=sum(ndcgs) / positive_count if positive_count else 0.0,
        negative_success_rate=negative_successes / negative_count if negative_count else 0.0,
        query_type_metrics=query_type_metrics,
        cpu_seconds=round(process_time() - cpu_started, 6),
        rss_mb=round(max(rss_samples) / (1024 * 1024), 3) if rss_samples else None,
        fixture_checksum=fixture_checksum,
        corpus_checksum=corpus_checksum,
        embedding_manifest_id=embedding_manifest_id,
    )


def run_repeated_benchmark(
    cases: list[QueryCase],
    searcher: Searcher,
    *,
    k: int = 8,
    repeats: int = 3,
    fixture_checksum: str | None = None,
    corpus_checksum: str | None = None,
    embedding_manifest_id: str | None = None,
) -> list[BenchmarkResult]:
    """Run the same benchmark repeatedly for variance-aware gate decisions."""

    if not 1 <= repeats <= 20:
        raise ValueError("repeats must be between 1 and 20")
    return [
        run_benchmark(
            cases,
            searcher,
            k=k,
            fixture_checksum=fixture_checksum,
            corpus_checksum=corpus_checksum,
            embedding_manifest_id=embedding_manifest_id,
        )
        for _ in range(repeats)
    ]


def run_concurrency_probe(
    cases: list[QueryCase],
    searcher: Searcher,
    *,
    k: int = 8,
    concurrency: int = 4,
    repetitions: int = 1,
    fixture_checksum: str | None = None,
    corpus_checksum: str | None = None,
    embedding_manifest_id: str | None = None,
) -> ConcurrencyResult:
    """Run a bounded concurrent probe without logging query or document text.

    This is an instrumentation primitive, not the final long-duration load test.
    The caller is responsible for selecting a representative fixture and for
    running separate cold/warm, filter-selectivity and server/local matrices.
    """

    if not cases:
        raise ValueError("cases cannot be empty")
    if not 1 <= k <= 100:
        raise ValueError("k must be between 1 and 100")
    if not 1 <= concurrency <= 64:
        raise ValueError("concurrency must be between 1 and 64")
    if not 1 <= repetitions <= 100:
        raise ValueError("repetitions must be between 1 and 100")

    total_requests = len(cases) * repetitions
    if total_requests > MAX_CONCURRENCY_PROBE_REQUESTS:
        raise ValueError(
            "concurrency probe request budget exceeded; reduce fixture size or repetitions"
        )
    work = cases * repetitions

    def execute(case: QueryCase) -> tuple[bool, float, str | None]:
        started = perf_counter()
        try:
            _search(searcher, case, limit=k)
            return True, (perf_counter() - started) * 1000, None
        except Exception as error:
            # Keep the probe privacy-safe: classify only the exception type,
            # never serialize its message (which may contain query text).
            return False, (perf_counter() - started) * 1000, type(error).__name__

    started = perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        outcomes = list(executor.map(execute, work))
    elapsed = perf_counter() - started
    latencies = sorted(latency for _, latency, _ in outcomes)

    def percentile(percent: float) -> float:
        index = max(0, min(len(latencies) - 1, ceil((percent / 100) * len(latencies)) - 1))
        return round(latencies[index], 3)

    successful = sum(success for success, _, _ in outcomes)
    error_types = Counter(
        error_type for _, _, error_type in outcomes if error_type is not None
    )
    return ConcurrencyResult(
        concurrency=concurrency,
        total_requests=len(outcomes),
        successful_requests=successful,
        error_count=len(outcomes) - successful,
        elapsed_seconds=round(elapsed, 6),
        throughput_per_second=round(len(outcomes) / elapsed, 3) if elapsed else 0.0,
        latency_p50_ms=percentile(50),
        latency_p95_ms=percentile(95),
        latency_p99_ms=percentile(99),
        error_types=dict(sorted(error_types.items())),
        fixture_checksum=fixture_checksum,
        corpus_checksum=corpus_checksum,
        embedding_manifest_id=embedding_manifest_id,
    )


def run_concurrency_matrix(
    cases: list[QueryCase],
    searcher: Searcher,
    concurrency_levels: Sequence[int],
    *,
    k: int = 8,
    repetitions: int = 1,
    fixture_checksum: str | None = None,
    corpus_checksum: str | None = None,
    embedding_manifest_id: str | None = None,
) -> list[ConcurrencyResult]:
    """Run bounded concurrency probes for distinct worker levels.

    The matrix is an orchestration helper, not a long-duration load generator;
    each level still passes through the single-probe request budget.
    """

    levels = list(concurrency_levels)
    if not levels:
        raise ValueError("concurrency levels cannot be empty")
    if len(levels) > MAX_CONCURRENCY_MATRIX_LEVELS:
        raise ValueError(
            f"concurrency matrix supports at most {MAX_CONCURRENCY_MATRIX_LEVELS} levels"
        )
    if len(set(levels)) != len(levels):
        raise ValueError("concurrency matrix levels must be unique")
    if any(not isinstance(level, int) for level in levels):
        raise ValueError("concurrency matrix levels must be integers")
    if not 1 <= k <= 100:
        raise ValueError("k must be between 1 and 100")
    if not 1 <= repetitions <= 100:
        raise ValueError("repetitions must be between 1 and 100")
    total_requests = len(cases) * repetitions * len(levels)
    if total_requests > MAX_CONCURRENCY_PROBE_REQUESTS:
        raise ValueError(
            "concurrency matrix request budget exceeded; reduce levels, fixture size or repetitions"
        )
    return [
        run_concurrency_probe(
            cases,
            searcher,
            k=k,
            concurrency=level,
            repetitions=repetitions,
            fixture_checksum=fixture_checksum,
            corpus_checksum=corpus_checksum,
            embedding_manifest_id=embedding_manifest_id,
        )
        for level in sorted(levels)
    ]


def write_concurrency_matrix_results(
    path: Path, results: Sequence[ConcurrencyResult]
) -> None:
    """Write a privacy-safe worker-level matrix without query or document text."""

    if not results:
        raise ValueError("concurrency matrix results cannot be empty")
    levels = [result.concurrency for result in results]
    if len(set(levels)) != len(levels):
        raise ValueError("concurrency matrix results must have unique levels")
    for result in results:
        validate_schema(result.to_dict(), "concurrency-result.schema.json")
    _ensure_provenance_consistency(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"runs": [result.to_dict() for result in results]}, indent=2),
        encoding="utf-8",
    )
