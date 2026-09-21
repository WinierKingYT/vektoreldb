import json
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from personal_vector_db.benchmark import (
    BenchmarkResult,
    QueryCase,
    assert_regression_within,
    choose_abstention_threshold,
    evaluate_abstention_threshold,
    fixture_coverage_report,
    load_query_cases,
    load_query_labels,
    merge_query_fixture_files,
    merge_query_label_files,
    recall_at_k,
    recall_regression_points,
    run_benchmark,
    run_concurrency_matrix,
    run_concurrency_probe,
    run_repeated_benchmark,
    summarize_benchmark_results,
    validate_fixture_requirements,
    write_benchmark_result,
    write_benchmark_results,
    write_concurrency_matrix_results,
    write_fixture_coverage_report,
    write_query_label_template,
)


@dataclass
class Result:
    chunk_id: str


class FakeSearcher:
    def search(self, query: str, *, limit: int = 8) -> list[Result]:
        return [Result("chunk-a")] if "a" in query else [Result("chunk-missing")]


def _write_synthetic_corpus_manifest(
    tmp_path: Path,
    *,
    parser_versions: tuple[str, ...] = ("plain-text-v1",),
    chunk_ids: tuple[str, ...] = ("chunk-a",),
    chunk_size_buckets: dict[str, str] | None = None,
    checksum: str = "sha256:" + "a" * 64,
) -> Path:
    manifest = {
        "schema_version": "corpus-manifest-v1",
        "root_name": "synthetic-test-sources",
        "corpus_checksum": checksum,
        "source_count": 1 if chunk_ids else 0,
        "parsed_source_count": 1 if chunk_ids else 0,
        "failed_source_count": 0,
        "total_bytes": 10 if chunk_ids else 0,
        "total_chunks": len(chunk_ids),
        "chunk_ids": list(chunk_ids),
        "chunk_size_buckets": chunk_size_buckets
        if chunk_size_buckets is not None
        else {chunk_id: "small" for chunk_id in chunk_ids},
        "chunking_version": "paragraph-pack-v2",
        "parser_versions": list(parser_versions),
        "privacy_classification": "private-local",
    }
    path = tmp_path / "corpus-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _write_synthetic_fixture_manifest(
    tmp_path: Path,
    *,
    corpus_checksum: str = "sha256:" + "a" * 64,
    parser_versions: tuple[str, ...] | None = ("plain-text-v1",),
    declare_provenance: bool = True,
) -> Path:
    versions = list(parser_versions or ())
    manifest = {
        "schema_version": "query-fixture-manifest-v1",
        "status": "contract-only",
        "minimum_query_count": 1,
        "recommended_split": {"development": 1.0},
        "split_tolerance": 0.05,
        "required_query_types": ["semantic"],
        "minimum_queries_per_type": 1,
        "required_document_size_buckets": ["small"],
        "required_filter_selectivity_buckets": ["low"],
        "corpus_checksum": corpus_checksum if declare_provenance else None,
        "parser_version": (versions[0] if len(versions) == 1 else "mixed")
        if declare_provenance and versions
        else None,
        "chunking_version": "paragraph-pack-v2" if declare_provenance else None,
        "embedding_manifest_id": None,
        "privacy_classification": "private-local",
        "notes": "Synthetic test manifest; contains no real corpus data.",
    }
    if declare_provenance and versions:
        manifest["parser_versions"] = versions
    path = tmp_path / "fixture-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_benchmark_reports_recall_and_query_count() -> None:
    cases = [
        QueryCase("q1", "a query", frozenset({"chunk-a"})),
        QueryCase("q2", "b query", frozenset({"chunk-b"})),
    ]

    result = run_benchmark(cases, FakeSearcher(), k=1)

    assert result.query_count == 2
    assert result.recall_at_k == 0.5
    assert result.elapsed_seconds >= 0
    assert result.latency_p50_ms >= 0
    assert result.latency_p95_ms >= result.latency_p50_ms
    assert result.latency_p99_ms >= result.latency_p95_ms
    assert result.error_rate == 0
    assert result.mrr_at_k == 0.5
    assert result.ndcg_at_k == 0.5
    assert result.cpu_seconds >= 0
    assert result.rss_mb is None or result.rss_mb > 0
    assert result.query_type_metrics["semantic"]["count"] == 2
    assert result.query_type_metrics["semantic"]["recall_at_k"] == 0.5


def test_benchmark_result_preserves_privacy_safe_provenance() -> None:
    cases = [
        QueryCase(
            query_id="q-provenance",
            text="a",
            relevant_chunk_ids=frozenset({"chunk-a"}),
            query_type="semantic",
        )
    ]

    result = run_benchmark(
        cases,
        FakeSearcher(),
        k=1,
        fixture_checksum="sha256:" + "a" * 64,
        corpus_checksum="sha256:" + "b" * 64,
        embedding_manifest_id="local-model-v1",
    )

    encoded = result.to_dict()
    assert encoded["fixture_checksum"] == "sha256:" + "a" * 64
    assert encoded["corpus_checksum"] == "sha256:" + "b" * 64
    assert encoded["embedding_manifest_id"] == "local-model-v1"
    assert "q-provenance" not in json.dumps(encoded["query_type_metrics"])


def test_merge_query_fixture_files_preserves_contract_fields(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(
        json.dumps(
            [
                {
                    "query_id": "q1",
                    "text": "ilk sorgu",
                    "relevant_chunk_ids": ["chunk-a"],
                    "query_type": "semantic",
                    "split": "development",
                }
            ]
        ),
        encoding="utf-8",
    )
    second.write_text(
        json.dumps(
            [
                {
                    "query_id": "q2",
                    "text": "ikinci sorgu",
                    "relevant_chunk_ids": [],
                    "query_type": "negative",
                    "split": "test",
                }
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "merged.json"

    summary = merge_query_fixture_files([first, second], output)

    assert summary == {"shard_count": 2, "query_count": 2}
    assert load_query_cases(output)[1].query_type == "negative"


def test_fixture_coverage_reports_corpus_size_buckets_separately(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    manifest = tmp_path / "manifest.json"
    corpus_manifest = tmp_path / "corpus.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "query_id": "q1",
                    "text": "soru",
                    "relevant_chunk_ids": [],
                    "query_type": "negative",
                    "split": "development",
                    "size_bucket": "small",
                }
            ]
        ),
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "query-fixture-manifest-v1",
                "status": "contract-only",
                "minimum_query_count": 1,
                "recommended_split": {"development": 1.0},
                "split_tolerance": 0.05,
                "required_query_types": ["negative"],
                "minimum_queries_per_type": 1,
                "required_document_size_buckets": ["small"],
                "required_filter_selectivity_buckets": [],
                "corpus_checksum": None,
                "parser_version": "plain-text-v1",
                "chunking_version": "paragraph-pack-v2",
                "embedding_manifest_id": "test",
                "privacy_classification": "private-local",
                "notes": "test manifest",
            }
        ),
        encoding="utf-8",
    )
    corpus_manifest.write_text(
        json.dumps(
            {
                "schema_version": "corpus-manifest-v1",
                "root_name": "sources",
                "corpus_checksum": "sha256:" + "a" * 64,
                "source_count": 1,
                "parsed_source_count": 1,
                "failed_source_count": 0,
                "total_bytes": 1,
                "total_chunks": 0,
                "total_extracted_chars": 0,
                "size_bucket_counts": {"small": 1, "medium": 0, "large": 0},
                "chunk_ids": [],
                "chunking_version": "paragraph-pack-v2",
                "parser_versions": ["plain-text-v1"],
                "privacy_classification": "private-local",
            }
        ),
        encoding="utf-8",
    )

    report = fixture_coverage_report(
        load_query_cases(fixture), manifest, corpus_manifest_path=corpus_manifest
    )

    assert report["size_bucket_counts"] == {"small": 1}
    assert report["corpus_size_bucket_counts"] == {
        "small": 1,
        "medium": 0,
        "large": 0,
    }


def test_fixture_coverage_rejects_size_bucket_binding_mismatch(tmp_path: Path) -> None:
    checksum = "sha256:" + "a" * 64
    corpus_path = _write_synthetic_corpus_manifest(
        tmp_path,
        chunk_size_buckets={"chunk-a": "medium"},
        checksum=checksum,
    )
    fixture_path = tmp_path / "fixture.json"
    manifest_path = _write_synthetic_fixture_manifest(tmp_path, corpus_checksum=checksum)
    fixture_path.write_text(
        json.dumps(
            [
                {
                    "query_id": "q1",
                    "text": "medium kaynağı small etiketiyle arama",
                    "relevant_chunk_ids": ["chunk-a"],
                    "query_type": "semantic",
                    "split": "development",
                    "size_bucket": "small",
                }
            ]
        ),
        encoding="utf-8",
    )

    report = fixture_coverage_report(
        load_query_cases(fixture_path),
        manifest_path,
        corpus_manifest_path=corpus_path,
    )

    assert report["chunk_size_bucket_binding_status"] == "mismatch"
    assert report["queries_with_size_bucket_mismatch"] == 1
    assert report["corpus_binding_status"] == "mismatch"


def test_fixture_coverage_rejects_partial_chunk_size_bucket_mapping(tmp_path: Path) -> None:
    checksum = "sha256:" + "a" * 64
    corpus_path = _write_synthetic_corpus_manifest(
        tmp_path,
        chunk_ids=("chunk-a", "chunk-b"),
        chunk_size_buckets={"chunk-a": "small"},
        checksum=checksum,
    )
    fixture_path = tmp_path / "fixture.json"
    manifest_path = _write_synthetic_fixture_manifest(tmp_path, corpus_checksum=checksum)
    fixture_path.write_text(
        json.dumps(
            [
                {
                    "query_id": "q1",
                    "text": "small kaynağı bul",
                    "relevant_chunk_ids": ["chunk-a"],
                    "query_type": "semantic",
                    "split": "development",
                    "size_bucket": "small",
                }
            ]
        ),
        encoding="utf-8",
    )

    report = fixture_coverage_report(
        load_query_cases(fixture_path),
        manifest_path,
        corpus_manifest_path=corpus_path,
    )

    assert report["chunk_size_bucket_binding_status"] == "mismatch"
    assert report["unknown_size_bucket_chunk_count"] == 1
    assert report["corpus_binding_status"] == "mismatch"


def test_merge_query_fixture_files_rejects_normalized_query_collision(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    payload = {
        "text": "Aynı   sorgu",
        "relevant_chunk_ids": ["chunk-a"],
        "query_type": "semantic",
        "split": "development",
    }
    first.write_text(json.dumps([{**payload, "query_id": "q1"}]), encoding="utf-8")
    second.write_text(json.dumps([{**payload, "query_id": "q2"}]), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate normalized query"):
        merge_query_fixture_files([first, second], tmp_path / "merged.json")


def test_merge_query_label_files_rejects_duplicate_query_id(tmp_path: Path) -> None:
    label = {
        "query_id": "q1",
        "relevant_chunk_ids": [],
        "annotator": "tester",
        "annotated_at": "2026-01-01T00:00:00Z",
        "source": "manual",
        "decision_note": "none",
        "corpus_checksum": "sha256:" + "a" * 64,
        "parser_version": "plain-text-v1",
        "chunking_version": "paragraph-pack-v2",
    }
    first = tmp_path / "first-labels.json"
    second = tmp_path / "second-labels.json"
    first.write_text(json.dumps([label]), encoding="utf-8")
    second.write_text(json.dumps([label]), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate query_id"):
        merge_query_label_files([first, second], tmp_path / "merged-labels.json")


def test_merge_query_label_files_rejects_incompatible_provenance(tmp_path: Path) -> None:
    base = {
        "relevant_chunk_ids": [],
        "annotator": "tester",
        "annotated_at": "2026-01-01T00:00:00Z",
        "source": "manual",
        "decision_note": "none",
        "parser_version": "plain-text-v1",
        "chunking_version": "paragraph-pack-v2",
    }
    first = tmp_path / "first-labels.json"
    second = tmp_path / "second-labels.json"
    first.write_text(
        json.dumps(
            [{**base, "query_id": "q1", "corpus_checksum": "sha256:" + "a" * 64}]
        ),
        encoding="utf-8",
    )
    second.write_text(
        json.dumps(
            [{**base, "query_id": "q2", "corpus_checksum": "sha256:" + "b" * 64}]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="incompatible provenance"):
        merge_query_label_files([first, second], tmp_path / "merged-labels.json")


def test_merge_query_label_files_normalizes_parser_version_order(tmp_path: Path) -> None:
    base = {
        "relevant_chunk_ids": [],
        "annotator": "tester",
        "annotated_at": "2026-01-01T00:00:00Z",
        "source": "manual",
        "decision_note": "none",
        "corpus_checksum": "sha256:" + "a" * 64,
        "parser_version": "mixed",
        "chunking_version": "paragraph-pack-v2",
    }
    first = tmp_path / "first-labels.json"
    second = tmp_path / "second-labels.json"
    first.write_text(
        json.dumps([{**base, "query_id": "q1", "parser_versions": ["html-v3", "csv-v1"]}]),
        encoding="utf-8",
    )
    second.write_text(
        json.dumps([{**base, "query_id": "q2", "parser_versions": ["csv-v1", "html-v3"]}]),
        encoding="utf-8",
    )

    result = merge_query_label_files([first, second], tmp_path / "merged-labels.json")

    assert result == {"shard_count": 2, "label_count": 2}


def test_recall_rejects_empty_cases() -> None:
    try:
        recall_at_k([], FakeSearcher())
    except ValueError as error:
        assert "empty" in str(error)
    else:
        raise AssertionError("empty benchmark cases must be rejected")


def test_repository_benchmark_fixture_has_thirty_cases() -> None:
    cases = load_query_cases(Path("data/benchmarks/queries.json"))

    assert len(cases) == 30
    assert len({case.query_id for case in cases}) == 30
    assert {case.query_type for case in cases} == {
        "semantic",
        "exact_identifier",
        "typo",
        "morphology",
        "long_context",
        "negative",
    }


def test_promtgen_experiment_fixture_has_target_size_and_negatives() -> None:
    cases = load_query_cases(Path("data/benchmarks/promtgen-readme-queries.json"))

    assert len(cases) == 100
    assert sum(case.query_type == "negative" for case in cases) == 11
    assert sum(case.query_type != "negative" for case in cases) == 89


def test_fixture_coverage_report_exposes_missing_buckets_without_final_rejection(
    tmp_path: Path,
) -> None:
    manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = fixture_coverage_report(
        [
            QueryCase(
                "q1",
                "query",
                frozenset(),
                query_type="negative",
                split="development",
                size_bucket="small",
                filter_selectivity="low",
            )
        ],
        manifest_path,
    )

    assert report["manifest_status"] == "contract-only"
    assert report["query_count"] == 1
    assert report["coverage_complete"] is False
    assert report["missing_query_types"] == [
        "semantic",
        "exact_identifier",
        "typo",
        "morphology",
        "long_context",
        "negative",
    ]
    assert report["missing_document_size_buckets"] == ["medium", "large"]
    assert report["missing_filter_selectivity_buckets"] == ["medium", "high"]
    assert report["missing_splits"] == ["test", "validation"]
    assert report["labels_status"] == "not-provided"
    assert report["unlabeled_query_count"] == 1


def test_fixture_coverage_report_counts_label_coverage_without_exposing_content(
    tmp_path: Path,
) -> None:
    manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(
        json.dumps(
            [
                {
                    "query_id": "q1",
                    "relevant_chunk_ids": [],
                    "annotator": "local-user",
                    "annotated_at": "2026-09-13T00:00:00Z",
                    "source": "manual",
                    "decision_note": "negative query",
                    "corpus_checksum": "sha256:" + "a" * 64,
                    "parser_version": "plain-text-v1",
                    "chunking_version": "paragraph-pack-v2",
                }
            ]
        ),
        encoding="utf-8",
    )

    report = fixture_coverage_report(
        [
            QueryCase(
                "q1",
                "secret query text",
                frozenset(),
                query_type="negative",
            ),
            QueryCase("q2", "another query", frozenset()),
        ],
        manifest_path,
        labels_path=labels_path,
    )

    assert report["labels_status"] == "incomplete"
    assert report["label_count"] == 1
    assert report["unlabeled_query_count"] == 1
    assert report["orphan_label_count"] == 0
    assert "secret query text" not in json.dumps(report)


def test_fixture_coverage_reports_stale_chunk_bindings_without_text(
    tmp_path: Path,
) -> None:
    manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    manifest_path = tmp_path / "fixture-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    corpus_path = tmp_path / "corpus-manifest.json"
    corpus_path.write_text(
        json.dumps(
            {
                "schema_version": "corpus-manifest-v1",
                "root_name": "sources",
                "corpus_checksum": "sha256:" + "a" * 64,
                "source_count": 1,
                "parsed_source_count": 1,
                "failed_source_count": 0,
                "total_bytes": 10,
                "total_chunks": 1,
                "chunk_ids": ["known-chunk"],
                "chunking_version": "paragraph-pack-v2",
                "parser_versions": ["plain-text-v1"],
                "privacy_classification": "private-local",
            }
        ),
        encoding="utf-8",
    )

    report = fixture_coverage_report(
        [QueryCase("q1", "private query", frozenset({"stale-chunk"}))],
        manifest_path,
        corpus_manifest_path=corpus_path,
    )

    assert report["corpus_binding_status"] == "mismatch"
    assert report["corpus_checksum_status"] == "not-declared"
    assert report["unknown_relevant_chunk_count"] == 1
    assert report["queries_with_unknown_relevant_chunks"] == 1
    assert report["coverage_complete"] is False
    assert "private query" not in json.dumps(report)


def test_fixture_coverage_reports_cross_split_duplicate_queries_without_text(
    tmp_path: Path,
) -> None:
    manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    manifest_path = tmp_path / "fixture-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = fixture_coverage_report(
        [
            QueryCase("q1", "  Aynı   soru ", frozenset(), split="development"),
            QueryCase("q2", "aynı soru", frozenset(), split="test"),
        ],
        manifest_path,
    )

    assert report["duplicate_query_group_count"] == 1
    assert report["duplicate_query_count"] == 1
    assert report["cross_split_duplicate_count"] == 1
    assert report["coverage_complete"] is False
    assert "aynı soru" not in json.dumps(report)


def test_fixture_validation_rejects_duplicate_normalized_queries(tmp_path: Path) -> None:
    manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    manifest.update(
        {
            "status": "ready",
            "corpus_checksum": "sha256:" + "d" * 64,
            "parser_version": "plain-text-v1",
            "chunking_version": "paragraph-pack-v2",
            "embedding_manifest_id": "local:model@revision",
        }
    )
    manifest_path = tmp_path / "fixture-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    cases = [
        QueryCase("q1", "aynı soru", frozenset(), split="development"),
        QueryCase("q2", " Aynı   Soru ", frozenset(), split="development"),
    ]

    with pytest.raises(ValueError, match="duplicate normalized queries"):
        validate_fixture_requirements(cases, manifest_path)


def test_fixture_coverage_accepts_matching_corpus_checksum_without_text(
    tmp_path: Path,
) -> None:
    manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    checksum = "sha256:" + "b" * 64
    manifest["corpus_checksum"] = checksum
    manifest_path = tmp_path / "fixture-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    corpus_path = tmp_path / "corpus-manifest.json"
    corpus_path.write_text(
        json.dumps(
            {
                "schema_version": "corpus-manifest-v1",
                "root_name": "sources",
                "corpus_checksum": checksum,
                "source_count": 1,
                "parsed_source_count": 1,
                "failed_source_count": 0,
                "total_bytes": 10,
                "total_chunks": 0,
                "chunk_ids": [],
                "chunking_version": "paragraph-pack-v2",
                "parser_versions": ["plain-text-v1"],
                "privacy_classification": "private-local",
            }
        ),
        encoding="utf-8",
    )

    report = fixture_coverage_report(
        [QueryCase("q1", "negative", frozenset(), query_type="negative")],
        manifest_path,
        corpus_manifest_path=corpus_path,
    )

    assert report["corpus_binding_status"] == "valid"
    assert report["corpus_checksum_status"] == "valid"


def test_fixture_coverage_reports_stale_label_chunk_bindings_without_text(
    tmp_path: Path,
) -> None:
    fixture_manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    fixture_path = tmp_path / "fixture-manifest.json"
    fixture_path.write_text(json.dumps(fixture_manifest), encoding="utf-8")
    corpus_path = tmp_path / "corpus-manifest.json"
    corpus_path.write_text(
        json.dumps(
            {
                "schema_version": "corpus-manifest-v1",
                "root_name": "sources",
                "corpus_checksum": "sha256:" + "c" * 64,
                "source_count": 1,
                "parsed_source_count": 1,
                "failed_source_count": 0,
                "total_bytes": 10,
                "total_chunks": 1,
                "chunk_ids": ["known-chunk"],
                "chunking_version": "paragraph-pack-v2",
                "parser_versions": ["plain-text-v1"],
                "privacy_classification": "private-local",
            }
        ),
        encoding="utf-8",
    )
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(
        json.dumps(
            [
                {
                    "query_id": "q1",
                    "relevant_chunk_ids": ["stale-label-chunk"],
                    "annotator": "local-user",
                    "annotated_at": "2026-09-13T00:00:00Z",
                    "source": "manual",
                    "decision_note": "review",
                    "corpus_checksum": "sha256:" + "c" * 64,
                    "parser_version": "plain-text-v1",
                    "chunking_version": "paragraph-pack-v2",
                }
            ]
        ),
        encoding="utf-8",
    )

    report = fixture_coverage_report(
        [QueryCase("q1", "ultra-private-query-text", frozenset())],
        fixture_path,
        labels_path=labels_path,
        corpus_manifest_path=corpus_path,
    )

    assert report["corpus_binding_status"] == "mismatch"
    assert report["unknown_labeled_chunk_count"] == 1
    assert report["labels_with_unknown_chunks"] == 1
    assert "ultra-private-query-text" not in json.dumps(report)


def test_query_label_template_preserves_ids_without_source_text(tmp_path: Path) -> None:
    output = tmp_path / "labels-template.json"
    cases = [QueryCase("q1", "private query", frozenset({"chunk-a"}))]

    write_query_label_template(output, cases)
    raw_text = output.read_text(encoding="utf-8")
    raw = json.loads(raw_text)

    assert raw[0]["query_id"] == "q1"
    assert raw[0]["relevant_chunk_ids"] == ["chunk-a"]
    assert raw[0]["source"] == "derived"
    assert "private query" not in raw_text


def test_query_label_template_uses_corpus_provenance(tmp_path: Path) -> None:
    output = tmp_path / "labels-template.json"
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            {
                "schema_version": "corpus-manifest-v1",
                "root_name": "sources",
                "corpus_checksum": "sha256:" + "a" * 64,
                "source_count": 0,
                "parsed_source_count": 0,
                "failed_source_count": 0,
                "total_bytes": 0,
                "total_chunks": 0,
                "chunk_ids": [],
                "privacy_classification": "private-local",
                "parser_versions": ["parser-v1"],
                "chunking_version": "paragraph-pack-v2",
            }
        ),
        encoding="utf-8",
    )

    write_query_label_template(
        output,
        [QueryCase("q1", "query", frozenset())],
        corpus_manifest_path=corpus,
    )
    label = json.loads(output.read_text(encoding="utf-8"))[0]

    assert label["corpus_checksum"] == "sha256:" + "a" * 64
    assert label["parser_version"] == "parser-v1"
    assert label["parser_versions"] == ["parser-v1"]


def test_query_label_template_preserves_mixed_parser_provenance(tmp_path: Path) -> None:
    output = tmp_path / "labels-template.json"
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            {
                "schema_version": "corpus-manifest-v1",
                "root_name": "sources",
                "corpus_checksum": "sha256:" + "b" * 64,
                "source_count": 0,
                "parsed_source_count": 0,
                "failed_source_count": 0,
                "total_bytes": 0,
                "total_chunks": 0,
                "chunk_ids": [],
                "privacy_classification": "private-local",
                "parser_versions": ["plain-text-v1", "html-v3"],
                "chunking_version": "paragraph-pack-v2",
            }
        ),
        encoding="utf-8",
    )

    write_query_label_template(
        output,
        [QueryCase("q1", "query", frozenset())],
        corpus_manifest_path=corpus,
    )
    label = json.loads(output.read_text(encoding="utf-8"))[0]

    assert label["parser_version"] == "mixed"
    assert label["parser_versions"] == ["html-v3", "plain-text-v1"]


def test_fixture_coverage_reports_label_provenance_mismatch(tmp_path: Path) -> None:
    versions = ("html-v4", "plain-text-v1")
    corpus_manifest = _write_synthetic_corpus_manifest(tmp_path, parser_versions=versions)
    fixture_manifest = _write_synthetic_fixture_manifest(
        tmp_path, parser_versions=versions
    )
    cases = [
        QueryCase(
            "q1", "synthetic query", frozenset({"chunk-a"}),
            split="development", size_bucket="small", filter_selectivity="low"
        )
    ]
    labels_path = tmp_path / "labels.json"
    write_query_label_template(labels_path, cases, corpus_manifest_path=corpus_manifest)
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    labels[0]["parser_versions"] = ["stale-parser-v1"]
    labels_path.write_text(json.dumps(labels), encoding="utf-8")

    report = fixture_coverage_report(
        cases,
        fixture_manifest,
        labels_path=labels_path,
        corpus_manifest_path=corpus_manifest,
    )

    assert report["label_provenance_status"] == "mismatch"
    assert report["label_provenance_mismatch_count"] == 1
    assert report["corpus_binding_status"] == "mismatch"


def test_fixture_coverage_reports_parser_version_sets(tmp_path: Path) -> None:
    expected = [
        "csv-v1",
        "email-v1",
        "html-v4",
        "json-v1",
        "jsonl-v1",
        "plain-text-v1",
        "rtf-v1",
        "xml-v1",
        "yaml-v1",
    ]
    versions = tuple(expected)
    corpus_manifest = _write_synthetic_corpus_manifest(tmp_path, parser_versions=versions)
    fixture_manifest = _write_synthetic_fixture_manifest(
        tmp_path, parser_versions=versions
    )
    cases = [
        QueryCase(
            "q1", "synthetic query", frozenset({"chunk-a"}),
            split="development", size_bucket="small", filter_selectivity="low"
        )
    ]
    labels_path = tmp_path / "labels.json"
    write_query_label_template(labels_path, cases, corpus_manifest_path=corpus_manifest)

    report = fixture_coverage_report(
        cases,
        fixture_manifest,
        labels_path=labels_path,
        corpus_manifest_path=corpus_manifest,
    )

    assert report["corpus_parser_versions"] == expected
    assert report["fixture_parser_versions"] == expected
    assert report["parser_versions_binding_status"] == "valid"


def test_fixture_coverage_rejects_parser_version_set_mismatch(tmp_path: Path) -> None:
    versions = ("plain-text-v1", "xml-v1")
    corpus_manifest = _write_synthetic_corpus_manifest(tmp_path, parser_versions=versions)
    manifest_path = _write_synthetic_fixture_manifest(
        tmp_path, parser_versions=("plain-text-v1",)
    )
    cases = [
        QueryCase(
            "q1", "synthetic query", frozenset({"chunk-a"}),
            split="development", size_bucket="small", filter_selectivity="low"
        )
    ]

    report = fixture_coverage_report(
        cases,
        manifest_path,
        corpus_manifest_path=corpus_manifest,
    )

    assert report["parser_versions_binding_status"] == "mismatch"
    assert report["corpus_binding_status"] == "mismatch"


def test_fixture_coverage_is_not_complete_without_declared_corpus_provenance(
    tmp_path: Path,
) -> None:
    manifest = {
        "schema_version": "query-fixture-manifest-v1",
        "status": "contract-only",
        "minimum_query_count": 1,
        "recommended_split": {"development": 1.0},
        "split_tolerance": 0.05,
        "required_query_types": ["semantic"],
        "minimum_queries_per_type": 1,
        "required_document_size_buckets": [],
        "required_filter_selectivity_buckets": [],
        "corpus_checksum": None,
        "parser_version": None,
        "chunking_version": None,
        "embedding_manifest_id": None,
        "privacy_classification": "private-local",
        "notes": "test manifest",
    }
    manifest_path = tmp_path / "fixture-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = fixture_coverage_report(
        [QueryCase("q1", "query", frozenset(), query_type="semantic", split="development")],
        manifest_path,
        corpus_manifest_path=_write_synthetic_corpus_manifest(tmp_path),
    )

    assert report["corpus_binding_status"] == "valid"
    assert report["corpus_checksum_status"] == "not-declared"
    assert report["parser_versions_binding_status"] == "not-declared"
    assert report["coverage_complete"] is False


def test_fixture_coverage_reports_corpus_binding_checksums(tmp_path: Path) -> None:
    checksum = "sha256:" + "a" * 64
    corpus_manifest = _write_synthetic_corpus_manifest(tmp_path, checksum=checksum)
    fixture_manifest = _write_synthetic_fixture_manifest(
        tmp_path, corpus_checksum=checksum
    )
    cases = [QueryCase("q1", "synthetic query", frozenset({"chunk-a"}))]
    report = fixture_coverage_report(
        cases,
        fixture_manifest,
        corpus_manifest_path=corpus_manifest,
    )

    assert report["corpus_checksum"] == checksum
    assert report["fixture_corpus_checksum"] == checksum


def test_fixture_coverage_preserves_optional_fixture_checksum() -> None:
    report = fixture_coverage_report(
        [QueryCase("q1", "query", frozenset())],
        Path("data/benchmarks/query-fixture-manifest.json"),
        fixture_checksum="sha256:" + "c" * 64,
    )

    assert report["fixture_checksum"] == "sha256:" + "c" * 64


def test_fixture_coverage_writer_rejects_incomplete_report(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="schema validation"):
        write_fixture_coverage_report(tmp_path / "coverage.json", {"query_count": 1})


def test_query_label_template_rejects_stale_chunk_references(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            {
                "schema_version": "corpus-manifest-v1",
                "root_name": "sources",
                "corpus_checksum": "sha256:" + "a" * 64,
                "source_count": 0,
                "parsed_source_count": 0,
                "failed_source_count": 0,
                "total_bytes": 0,
                "total_chunks": 0,
                "chunk_ids": [],
                "chunking_version": "paragraph-pack-v2",
                "parser_versions": ["plain-text-v1"],
                "privacy_classification": "private-local",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="outside the corpus manifest"):
        write_query_label_template(
            tmp_path / "labels.json",
            [QueryCase("q1", "query", frozenset({"stale-chunk"}))],
            corpus_manifest_path=corpus,
        )


def test_fixture_coverage_marks_derived_labels_as_review_required(tmp_path: Path) -> None:
    manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    labels_path = tmp_path / "labels.json"
    corpus_path = _write_synthetic_corpus_manifest(tmp_path, chunk_ids=())
    write_query_label_template(
        labels_path,
        [QueryCase("q1", "query", frozenset())],
        corpus_manifest_path=corpus_path,
    )

    report = fixture_coverage_report(
        [QueryCase("q1", "query", frozenset())],
        manifest_path,
        labels_path=labels_path,
    )

    assert report["labels_status"] == "review-required"
    assert report["review_required_label_count"] == 1


def test_benchmark_loader_rejects_duplicate_ids_and_invalid_negative_cases(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '[{"query_id":"q1","text":"one","relevant_chunk_ids":[]},'
        '{"query_id":"q1","text":"two","relevant_chunk_ids":[]}]',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_query_cases(duplicate)

    invalid_negative = tmp_path / "negative.json"
    invalid_negative.write_text(
        '[{"query_id":"q1","text":"unknown","relevant_chunk_ids":["chunk-a"],'
        '"query_type":"negative"}]',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="negative"):
        load_query_cases(invalid_negative)


def test_benchmark_loader_parses_allowlisted_filters(tmp_path: Path) -> None:
    fixture = tmp_path / "filtered.json"
    fixture.write_text(
        '[{"query_id":"q1","text":"query","relevant_chunk_ids":[],'
        '"query_type":"negative","filters":{"source_types":["markdown"]}}]',
        encoding="utf-8",
    )

    case = load_query_cases(fixture)[0]

    assert case.filters is not None
    assert case.filters.source_types == ("markdown",)


def test_benchmark_loader_rejects_unknown_filter_fields(tmp_path: Path) -> None:
    fixture = tmp_path / "invalid-filter.json"
    fixture.write_text(
        '[{"query_id":"q1","text":"query","relevant_chunk_ids":[],'
        '"filters":{"owner_id":["someone-else"]}}]',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="filters"):
        load_query_cases(fixture)


def test_fixture_manifest_schema_rejects_unknown_fields(tmp_path: Path) -> None:
    manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    manifest["unexpected"] = True
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="schema validation"):
        validate_fixture_requirements(
            [QueryCase("q1", "query", frozenset())], path
        )


def test_fixture_validation_can_bind_to_corpus_manifest(tmp_path: Path) -> None:
    manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    manifest.update(
        {
            "status": "ready",
            "corpus_checksum": "sha256:" + "a" * 64,
            "parser_version": "plain-text-v1",
            "chunking_version": "paragraph-pack-v2",
            "embedding_manifest_id": "local:model@revision",
        }
    )
    fixture_manifest = tmp_path / "fixture-manifest.json"
    fixture_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    corpus_manifest = {
        "schema_version": "corpus-manifest-v1",
        "root_name": "sources",
        "corpus_checksum": "sha256:" + "a" * 64,
        "source_count": 1,
        "parsed_source_count": 1,
        "failed_source_count": 0,
        "total_bytes": 10,
        "total_chunks": 1,
        "chunk_ids": ["chunk-a"],
        "chunking_version": "paragraph-pack-v2",
        "parser_versions": ["plain-text-v1"],
        "privacy_classification": "private-local",
    }
    corpus_path = tmp_path / "corpus-manifest.json"
    corpus_path.write_text(json.dumps(corpus_manifest), encoding="utf-8")
    inconsistent_corpus_path = tmp_path / "inconsistent-corpus-manifest.json"
    inconsistent_corpus = {**corpus_manifest, "total_chunks": 2}
    inconsistent_corpus_path.write_text(json.dumps(inconsistent_corpus), encoding="utf-8")
    cases = [
        QueryCase(
            "q1",
            "query",
            frozenset({"chunk-a"}),
            split="development",
            size_bucket="small",
            filter_selectivity="low",
        )
    ]
    mismatched_fixture = {**manifest, "chunking_version": "paragraph-pack-v1"}
    mismatched_fixture_path = tmp_path / "mismatched-fixture-manifest.json"
    mismatched_fixture_path.write_text(json.dumps(mismatched_fixture), encoding="utf-8")
    with pytest.raises(ValueError, match="chunking_version does not match"):
        validate_fixture_requirements(cases, mismatched_fixture_path, corpus_path)
    with pytest.raises(ValueError, match="total_chunks does not match chunk_ids"):
        validate_fixture_requirements(cases, fixture_manifest, inconsistent_corpus_path)
    unknown_cases = [
        QueryCase(
            "q-unknown",
            "query",
            frozenset({"missing-chunk"}),
            split="development",
            size_bucket="small",
            filter_selectivity="low",
        )
    ]
    with pytest.raises(ValueError, match="unknown chunk_ids"):
        validate_fixture_requirements(unknown_cases, fixture_manifest, corpus_path)
    with pytest.raises(ValueError, match="at least 300"):
        validate_fixture_requirements(cases, fixture_manifest, corpus_path)


def test_fixture_validation_distinguishes_missing_corpus_checksum(
    tmp_path: Path,
) -> None:
    manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    fixture_path = tmp_path / "fixture-manifest.json"
    fixture_path.write_text(json.dumps(manifest), encoding="utf-8")
    corpus_path = tmp_path / "corpus-manifest.json"
    corpus_path.write_text(
        json.dumps(
            {
                "schema_version": "corpus-manifest-v1",
                "root_name": "sources",
                "corpus_checksum": "sha256:" + "a" * 64,
                "source_count": 0,
                "parsed_source_count": 0,
                "failed_source_count": 0,
                "total_bytes": 0,
                "total_chunks": 0,
                "chunk_ids": [],
                "chunking_version": "paragraph-pack-v2",
                "parser_versions": ["plain-text-v1"],
                "privacy_classification": "private-local",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="checksum is required"):
        validate_fixture_requirements(
            [QueryCase("q1", "query", frozenset())], fixture_path, corpus_path
        )


def test_fixture_validation_rejects_skewed_split_distribution(tmp_path: Path) -> None:
    manifest = json.loads(
        Path("data/benchmarks/query-fixture-manifest.json").read_text(encoding="utf-8")
    )
    manifest.update(
        {
            "status": "ready",
            "corpus_checksum": "sha256:" + "b" * 64,
            "parser_version": "plain-text-v1",
            "chunking_version": "paragraph-pack-v1",
            "embedding_manifest_id": "local:model@revision",
        }
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    query_types = ["semantic", "exact_identifier", "typo", "morphology", "long_context", "negative"]
    cases = [
        QueryCase(
            f"q{index}",
            f"query-{index}",
            frozenset() if query_type == "negative" else frozenset({"chunk-a"}),
            query_type,
            split="development" if index < 250 else "validation" if index < 275 else "test",
            size_bucket=("small", "medium", "large")[index % 3],
            filter_selectivity=("low", "medium", "high")[index % 3],
        )
        for index in range(300)
        for query_type in [query_types[index % len(query_types)]]
    ]

    with pytest.raises(ValueError, match="split development ratio"):
        validate_fixture_requirements(cases, manifest_path)


def test_query_labels_validate_as_separate_annotation_records(tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(
        json.dumps(
            [
                {
                    "query_id": "q1",
                    "relevant_chunk_ids": ["chunk-a"],
                    "annotator": "local-user",
                    "annotated_at": "2026-09-13T00:00:00Z",
                    "source": "manual",
                    "decision_note": "Direct answer evidence",
                    "corpus_checksum": "sha256:" + "c" * 64,
                    "parser_version": "plain-text-v1",
                    "chunking_version": "paragraph-pack-v1",
                }
            ]
        ),
        encoding="utf-8",
    )

    labels = load_query_labels(labels_path)

    assert labels["q1"]["annotator"] == "local-user"


def test_fixture_validation_binds_labels_to_case_and_manifest(tmp_path: Path) -> None:
    checksum = "sha256:" + "d" * 64
    manifest = {
        "schema_version": "query-fixture-manifest-v1",
        "status": "ready",
        "minimum_query_count": 1,
        "recommended_split": {"development": 1.0},
        "split_tolerance": 0.01,
        "required_query_types": ["semantic"],
        "minimum_queries_per_type": 1,
        "required_document_size_buckets": ["small"],
        "required_filter_selectivity_buckets": ["low"],
        "corpus_checksum": checksum,
        "parser_version": "plain-text-v1",
        "chunking_version": "paragraph-pack-v1",
        "embedding_manifest_id": "local:model@revision",
        "privacy_classification": "private-local",
        "notes": "test",
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(
        json.dumps(
            [
                {
                    "query_id": "q1",
                    "relevant_chunk_ids": ["chunk-a"],
                    "annotator": "local-user",
                    "annotated_at": "2026-09-13T00:00:00Z",
                    "source": "manual",
                    "decision_note": "direct evidence",
                    "corpus_checksum": checksum,
                    "parser_version": "plain-text-v1",
                    "chunking_version": "paragraph-pack-v1",
                }
            ]
        ),
        encoding="utf-8",
    )
    corpus_path = tmp_path / "corpus-manifest.json"
    corpus_path.write_text(
        json.dumps(
            {
                "schema_version": "corpus-manifest-v1",
                "root_name": "sources",
                "corpus_checksum": checksum,
                "source_count": 1,
                "parsed_source_count": 1,
                "failed_source_count": 0,
                "total_bytes": 10,
                "total_chunks": 1,
                "chunk_ids": ["chunk-a"],
                "chunk_size_buckets": {"chunk-a": "small"},
                "chunking_version": "paragraph-pack-v1",
                "parser_versions": ["plain-text-v1"],
                "privacy_classification": "private-local",
            }
        ),
        encoding="utf-8",
    )

    summary = validate_fixture_requirements(
        [
            QueryCase(
                "q1",
                "query",
                frozenset({"chunk-a"}),
                split="development",
                size_bucket="small",
                filter_selectivity="low",
            )
        ],
        manifest_path,
        corpus_manifest_path=corpus_path,
        labels_path=labels_path,
    )

    assert summary["label_count"] == 1


def test_ready_fixture_rejects_unreviewed_derived_labels(tmp_path: Path) -> None:
    checksum = "sha256:" + "e" * 64
    manifest = {
        "schema_version": "query-fixture-manifest-v1",
        "status": "ready",
        "minimum_query_count": 1,
        "recommended_split": {"development": 1.0},
        "split_tolerance": 0.01,
        "required_query_types": ["semantic"],
        "minimum_queries_per_type": 1,
        "required_document_size_buckets": ["small"],
        "required_filter_selectivity_buckets": ["low"],
        "corpus_checksum": checksum,
        "parser_version": "plain-text-v1",
        "chunking_version": "paragraph-pack-v1",
        "embedding_manifest_id": "local:model@revision",
        "privacy_classification": "private-local",
        "notes": "test",
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(
        json.dumps(
            [
                {
                    "query_id": "q1",
                    "relevant_chunk_ids": ["chunk-a"],
                    "annotator": "generator",
                    "annotated_at": "2026-09-13T00:00:00Z",
                    "source": "derived",
                    "decision_note": "generated candidate",
                    "corpus_checksum": checksum,
                    "parser_version": "plain-text-v1",
                    "chunking_version": "paragraph-pack-v1",
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires review"):
        validate_fixture_requirements(
            [
                QueryCase(
                    "q1",
                    "query",
                    frozenset({"chunk-a"}),
                    split="development",
                    size_bucket="small",
                    filter_selectivity="low",
                )
            ],
            manifest_path,
            labels_path=labels_path,
        )


def test_ready_fixture_requires_label_file_after_other_gates_pass(tmp_path: Path) -> None:
    checksum = "sha256:" + "f" * 64
    manifest = {
        "schema_version": "query-fixture-manifest-v1",
        "status": "ready",
        "minimum_query_count": 1,
        "recommended_split": {"development": 1.0},
        "split_tolerance": 0.01,
        "required_query_types": ["semantic"],
        "minimum_queries_per_type": 1,
        "required_document_size_buckets": ["small"],
        "required_filter_selectivity_buckets": ["low"],
        "corpus_checksum": checksum,
        "parser_version": "plain-text-v1",
        "chunking_version": "paragraph-pack-v1",
        "embedding_manifest_id": "local:model@revision",
        "privacy_classification": "private-local",
        "notes": "test",
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    cases = [
        QueryCase(
            "q1",
            "query",
            frozenset({"chunk-a"}),
            query_type="semantic",
            split="development",
            size_bucket="small",
            filter_selectivity="low",
        )
    ]

    with pytest.raises(ValueError, match="requires a label file"):
        validate_fixture_requirements(cases, manifest_path)

    labels_path = tmp_path / "labels.json"
    labels_path.write_text(
        json.dumps(
            [
                {
                    "query_id": "q1",
                    "relevant_chunk_ids": ["chunk-a"],
                    "annotator": "local-user",
                    "annotated_at": "2026-09-22T00:00:00Z",
                    "source": "manual",
                    "decision_note": "direct evidence",
                    "corpus_checksum": checksum,
                    "parser_version": "plain-text-v1",
                    "chunking_version": "paragraph-pack-v1",
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="requires a corpus manifest"):
        validate_fixture_requirements(cases, manifest_path, labels_path=labels_path)


def test_benchmark_result_can_be_written(tmp_path: Path) -> None:
    result = run_benchmark(
        [QueryCase("q1", "a", frozenset({"chunk-a"}))], FakeSearcher(), k=1
    )
    output = tmp_path / "results" / "run.json"

    write_benchmark_result(output, result)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["query_count"] == 1
    assert "cpu_seconds" in payload
    assert "rss_mb" in payload


def test_benchmark_writer_rejects_invalid_schema_before_writing(tmp_path: Path) -> None:
    result = run_benchmark(
        [QueryCase("q1", "a", frozenset({"chunk-a"}))], FakeSearcher(), k=1
    )
    output = tmp_path / "invalid.json"

    with pytest.raises(ValueError, match="schema validation"):
        write_benchmark_result(output, replace(result, recall_at_k=1.5))

    assert not output.exists()


def test_repeated_benchmark_and_output_preserve_each_run(tmp_path: Path) -> None:
    cases = [QueryCase("q1", "a", frozenset({"chunk-a"}))]

    results = run_repeated_benchmark(cases, FakeSearcher(), k=1, repeats=3)
    output = tmp_path / "results" / "repeated.json"
    write_benchmark_results(output, results)

    assert len(results) == 3
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload["runs"]) == 3
    assert payload["summary"]["run_count"] == 3
    assert payload["summary"]["metrics"]["recall_at_k"]["mean"] == 1.0


def test_repeated_benchmark_aggregate_rejects_mixed_provenance(tmp_path: Path) -> None:
    cases = [QueryCase("q1", "a", frozenset({"chunk-a"}))]
    first = run_benchmark(
        cases,
        FakeSearcher(),
        k=1,
        fixture_checksum="sha256:" + "a" * 64,
    )
    second = replace(first, fixture_checksum="sha256:" + "b" * 64)

    with pytest.raises(ValueError, match="same fixture_checksum"):
        write_benchmark_results(tmp_path / "mixed.json", [first, second])


def test_benchmark_summary_rejects_mixed_query_counts() -> None:
    results = [
        BenchmarkResult(1, 1.0, 0.1, 1.0, 2.0, 3.0, 0.0, 1.0, 1.0),
        BenchmarkResult(2, 1.0, 0.1, 1.0, 2.0, 3.0, 0.0, 1.0, 1.0),
    ]

    with pytest.raises(ValueError, match="same query count"):
        summarize_benchmark_results(results)


def test_repeated_benchmark_rejects_invalid_repeat_count() -> None:
    with pytest.raises(ValueError, match="between 1 and 20"):
        run_repeated_benchmark(
            [QueryCase("q1", "a", frozenset({"chunk-a"}))], FakeSearcher(), repeats=0
        )


def test_benchmark_counts_search_errors() -> None:
    class FailingSearcher:
        def search(self, query: str, *, limit: int = 8) -> list[Result]:
            raise RuntimeError("temporary failure")

    result = run_benchmark(
        [QueryCase("q1", "a", frozenset({"chunk-a"}))], FailingSearcher(), k=1
    )

    assert result.recall_at_k == 0
    assert result.error_rate == 1
    assert result.mrr_at_k == 0
    assert result.ndcg_at_k == 0


def test_benchmark_reports_negative_query_success_separately() -> None:
    class PositiveAndNoHitSearcher:
        def search(self, query: str, *, limit: int = 8) -> list[Result]:
            return [Result("chunk-a")] if query == "a" else []

    cases = [
        QueryCase("positive", "a", frozenset({"chunk-a"})),
        QueryCase("negative", "none", frozenset(), "negative"),
    ]

    result = run_benchmark(cases, PositiveAndNoHitSearcher(), k=1)

    assert result.recall_at_k == 1.0
    assert result.negative_success_rate == 1.0
    assert result.query_type_metrics["negative"]["negative_success_rate"] == 1.0
    assert result.query_type_metrics["semantic"]["mrr_at_k"] == 1.0


def test_abstention_threshold_evaluation_is_type_aware_and_privacy_safe() -> None:
    cases = [
        QueryCase("positive-1", "private-a", frozenset({"chunk-a"})),
        QueryCase("positive-2", "private-b", frozenset({"chunk-b"})),
        QueryCase("negative-1", "private-c", frozenset(), query_type="negative"),
        QueryCase("negative-2", "private-d", frozenset(), query_type="negative"),
    ]

    result = evaluate_abstention_threshold(
        cases, [[0.95], [0.8], [0.3], []], threshold=0.8
    )

    assert result.positive_acceptance_rate == 1.0
    assert result.negative_success_rate == 1.0
    assert result.false_abstention_rate == 0.0
    assert result.to_dict()["threshold"] == 0.8
    assert "private-a" not in str(result.to_dict())


def test_abstention_threshold_selector_chooses_highest_feasible_floor() -> None:
    cases = [
        QueryCase("positive-1", "one", frozenset({"chunk-a"})),
        QueryCase("positive-2", "two", frozenset({"chunk-b"})),
        QueryCase("negative-1", "three", frozenset(), query_type="negative"),
        QueryCase("negative-2", "four", frozenset(), query_type="negative"),
    ]

    result = choose_abstention_threshold(
        cases,
        [[0.95], [0.8], [0.3], [0.2]],
        min_positive_acceptance=0.5,
        min_negative_success=1.0,
    )

    assert result.threshold == 0.95
    assert result.positive_acceptance_rate == 0.5
    assert result.negative_success_rate == 1.0


def test_abstention_threshold_rejects_invalid_scores_and_unsatisfiable_floor() -> None:
    case = [QueryCase("q1", "query", frozenset())]
    with pytest.raises(ValueError, match="scores"):
        evaluate_abstention_threshold(case, [[float("nan")]], threshold=0.5)
    with pytest.raises(ValueError, match="no abstention threshold"):
        choose_abstention_threshold(
            [
                QueryCase("positive", "query", frozenset({"chunk-a"})),
                QueryCase("negative", "other", frozenset(), query_type="negative"),
            ],
            [[0.2], [0.9]],
            min_positive_acceptance=1.0,
            min_negative_success=1.0,
        )


def test_abstention_threshold_rejects_non_numeric_and_boolean_scores() -> None:
    cases = [QueryCase("positive", "query", frozenset({"chunk-a"}))]

    with pytest.raises(ValueError, match="scores must be finite"):
        evaluate_abstention_threshold(cases, [["0.9"]], threshold=0.5)  # type: ignore[list-item]
    with pytest.raises(ValueError, match="scores must be finite"):
        evaluate_abstention_threshold(cases, [[True]], threshold=0.5)  # type: ignore[list-item]
    with pytest.raises(ValueError, match="threshold must be"):
        evaluate_abstention_threshold(cases, [[0.9]], threshold=True)


@pytest.mark.parametrize("score", [True, "0.9"])
def test_abstention_threshold_selector_rejects_invalid_score_types(score: object) -> None:
    cases = [QueryCase("positive", "query", frozenset({"chunk-a"}))]

    with pytest.raises(ValueError, match="scores must be finite"):
        choose_abstention_threshold(
            cases, [[score]], min_positive_acceptance=1.0  # type: ignore[list-item]
        )


@pytest.mark.parametrize("floor", [True, "0.9"])
def test_abstention_threshold_selector_rejects_invalid_quality_floor_types(
    floor: object,
) -> None:
    cases = [QueryCase("positive", "query", frozenset({"chunk-a"}))]

    with pytest.raises(ValueError, match="min_positive_acceptance"):
        choose_abstention_threshold(
            cases,
            [[0.9]],
            min_positive_acceptance=floor,  # type: ignore[arg-type]
        )


def test_concurrency_probe_reports_success_and_errors_without_text() -> None:
    class SometimesFailingSearcher:
        def search(self, query: str, *, limit: int = 8) -> list[Result]:
            if query == "fail":
                raise RuntimeError("temporary")
            return [Result("chunk-a")]

    cases = [
        QueryCase("ok", "ok", frozenset({"chunk-a"})),
        QueryCase("bad", "fail", frozenset()),
    ]

    result = run_concurrency_probe(
        cases, SometimesFailingSearcher(), k=1, concurrency=2, repetitions=2
    )

    assert result.total_requests == 4
    assert result.k == 1
    assert result.repetitions == 2
    assert result.successful_requests == 2
    assert result.error_count == 2
    assert result.error_types == {"RuntimeError": 2}
    assert "temporary" not in str(result.to_dict())
    assert result.throughput_per_second > 0
    assert result.latency_p99_ms >= result.latency_p50_ms


def test_concurrency_result_preserves_privacy_safe_provenance() -> None:
    cases = [QueryCase("q-provenance", "a", frozenset({"chunk-a"}))]

    result = run_concurrency_probe(
        cases,
        FakeSearcher(),
        k=1,
        concurrency=1,
        fixture_checksum="sha256:" + "a" * 64,
        corpus_checksum="sha256:" + "b" * 64,
        embedding_manifest_id="local-model-v1",
    )

    encoded = result.to_dict()
    assert encoded["fixture_checksum"] == "sha256:" + "a" * 64
    assert encoded["corpus_checksum"] == "sha256:" + "b" * 64
    assert encoded["embedding_manifest_id"] == "local-model-v1"
    assert "q-provenance" not in json.dumps(encoded)


def test_concurrency_probe_rejects_out_of_range_settings() -> None:
    with pytest.raises(ValueError, match="concurrency"):
        run_concurrency_probe(
            [QueryCase("q1", "query", frozenset())], FakeSearcher(), concurrency=65
        )


def test_concurrency_probe_rejects_excessive_total_request_budget() -> None:
    with pytest.raises(ValueError, match="request budget"):
        run_concurrency_probe(
            [QueryCase(f"q{index}", "query", frozenset()) for index in range(1_001)],
            FakeSearcher(),
            repetitions=100,
        )


def test_concurrency_matrix_runs_sorted_unique_levels() -> None:
    results = run_concurrency_matrix(
        [QueryCase("q1", "a", frozenset())],
        FakeSearcher(),
        [4, 1, 2],
        repetitions=1,
    )

    assert [result.concurrency for result in results] == [1, 2, 4]


def test_concurrency_matrix_rejects_duplicate_levels() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        run_concurrency_matrix(
            [QueryCase("q1", "a", frozenset())], FakeSearcher(), [1, 1]
        )


def test_concurrency_matrix_rejects_excessive_total_request_budget() -> None:
    with pytest.raises(ValueError, match="matrix request budget"):
        run_concurrency_matrix(
            [QueryCase(f"q{index}", "query", frozenset()) for index in range(1_001)],
            FakeSearcher(),
            [1, 2],
            repetitions=100,
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"k": 0}, "k"), ({"repetitions": 0}, "repetitions")],
)
def test_concurrency_matrix_rejects_invalid_probe_settings(
    kwargs: dict[str, int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        run_concurrency_matrix(
            [QueryCase("q1", "query", frozenset())],
            FakeSearcher(),
            [1, 2],
            **kwargs,
        )


def test_concurrency_matrix_writer_preserves_runs_without_text(tmp_path: Path) -> None:
    results = run_concurrency_matrix(
        [QueryCase("q1", "gizli-sorgu-123", frozenset())], FakeSearcher(), [1, 2]
    )
    output = tmp_path / "matrix.json"

    write_concurrency_matrix_results(output, results)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [run["concurrency"] for run in payload["runs"]] == [1, 2]
    assert "gizli-sorgu-123" not in output.read_text(encoding="utf-8")


def test_concurrency_matrix_writer_rejects_mixed_provenance(tmp_path: Path) -> None:
    cases = [QueryCase("q1", "query", frozenset())]
    results = run_concurrency_matrix(
        cases,
        FakeSearcher(),
        [1, 2],
        fixture_checksum="sha256:" + "a" * 64,
    )
    results[1] = replace(results[1], fixture_checksum="sha256:" + "b" * 64)

    with pytest.raises(ValueError, match="same fixture_checksum"):
        write_concurrency_matrix_results(tmp_path / "mixed-matrix.json", results)


def test_concurrency_writer_rejects_invalid_schema_before_writing(tmp_path: Path) -> None:
    result = run_concurrency_probe(
        [QueryCase("q1", "query", frozenset())], FakeSearcher(), concurrency=1
    )
    output = tmp_path / "invalid-matrix.json"

    with pytest.raises(ValueError, match="schema validation"):
        write_concurrency_matrix_results(output, [replace(result, error_count=-1)])

    assert not output.exists()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda result: replace(result, error_count=result.error_count + 1), "request counts"),
        (
            lambda result: replace(result, error_types={"RuntimeError": 99}),
            "error types",
        ),
        (lambda result: replace(result, latency_p95_ms=0.0), "percentiles"),
        (
            lambda result: replace(result, elapsed_seconds=1.0, throughput_per_second=0.0),
            "throughput",
        ),
    ],
)
def test_concurrency_writer_rejects_inconsistent_metrics(
    tmp_path: Path, mutation, message: str
) -> None:
    result = run_concurrency_probe(
        [QueryCase("q1", "query", frozenset())], FakeSearcher(), concurrency=1
    )

    with pytest.raises(ValueError, match=message):
        write_concurrency_matrix_results(tmp_path / "invalid-metrics.json", [mutation(result)])

    assert not (tmp_path / "invalid-metrics.json").exists()


def test_concurrency_probe_budget_check_happens_before_work_expansion() -> None:
    class ExplodingCases(list):
        def __mul__(self, _other):
            raise AssertionError("work must not be expanded")

    with pytest.raises(ValueError, match="request budget"):
        run_concurrency_probe(
            ExplodingCases(
                QueryCase(f"q{index}", "query", frozenset()) for index in range(1_001)
            ),
            FakeSearcher(),
            repetitions=100,
        )


def test_benchmark_enforces_recall_regression_budget() -> None:
    baseline = BenchmarkResult(10, 0.9, 0, 0, 0, 0, 0, 0, 0)
    candidate = BenchmarkResult(10, 0.7, 0, 0, 0, 0, 0, 0, 0)

    assert recall_regression_points(baseline, candidate) == pytest.approx(20.0)
    try:
        assert_regression_within(baseline, candidate, max_points=2)
    except AssertionError as error:
        assert "exceeds" in str(error)
    else:
        raise AssertionError("recall regression budget must be enforced")
