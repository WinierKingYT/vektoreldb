"""Command-line interface for local ingest and retrieval."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from .backup import read_backup_manifest, write_backup_manifest
from .benchmark import (
    fixture_coverage_report,
    load_query_cases,
    merge_query_fixture_files,
    merge_query_label_files,
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
from .config import Settings, validate_runtime_settings
from .corpus import (
    count_excluded_files,
    read_corpus_manifest,
    summarize_unsupported_files,
    write_corpus_inventory,
    write_corpus_manifest,
)
from .embeddings import create_embedding_provider
from .ingest import IngestService, validate_document_id
from .planner import SelectivityQueryPlanner
from .reranking import LexicalOverlapReranker
from .retrieval import RetrievalService
from .storage import (
    QdrantHybridVectorStore,
    QdrantLateInteractionVectorStore,
    QdrantQuantizedVectorStore,
    QdrantVectorStore,
)


def _configure_utf8_output() -> None:
    """Keep Turkish and other Unicode source text printable on Windows consoles."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                # Test capture streams and embedded consoles may not support it.
                pass


def _collection_name(settings: Settings) -> str:
    return {
        "dense": settings.collection_name,
        "hybrid": settings.hybrid_collection_name,
        "late": settings.late_collection_name,
        "quantized": settings.quantized_collection_name,
    }[settings.retrieval_mode]


def _services(settings: Settings) -> tuple[object, QdrantVectorStore]:
    validate_runtime_settings(settings)
    provider = create_embedding_provider(settings)
    store_type = {
        "dense": QdrantVectorStore,
        "hybrid": QdrantHybridVectorStore,
        "late": QdrantLateInteractionVectorStore,
        "quantized": QdrantQuantizedVectorStore,
    }[settings.retrieval_mode]
    store = store_type(settings.qdrant_url, _collection_name(settings), hnsw_ef=settings.hnsw_ef)
    store.ensure_collection(settings.vector_dimension)
    store.ensure_manifest(provider.manifest.manifest_id)
    return provider, store


def _reranker(settings: Settings):
    return LexicalOverlapReranker() if settings.reranker_mode == "lexical" else None


def _planner(settings: Settings):
    return SelectivityQueryPlanner() if settings.query_planner_mode == "selectivity" else None


def _validate_fixture_or_exit(
    cases: list[object],
    manifest: Path,
    *,
    corpus_manifest: Path | None = None,
    labels: Path | None = None,
) -> dict[str, object]:
    try:
        return validate_fixture_requirements(
            cases,
            manifest,
            corpus_manifest_path=corpus_manifest,
            labels_path=labels,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"fixture validation failed: {error}", file=sys.stderr)
        raise SystemExit(2) from None


def _load_fixture_or_exit(path: Path) -> list[object]:
    try:
        return load_query_cases(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"fixture loading failed: {error}", file=sys.stderr)
        raise SystemExit(2) from None


def _fixture_coverage_or_exit(
    cases: list[object],
    manifest: Path,
    labels: Path | None = None,
    corpus_manifest: Path | None = None,
    fixture_checksum: str | None = None,
) -> dict[str, object]:
    try:
        return fixture_coverage_report(
            cases,
            manifest,
            labels_path=labels,
            corpus_manifest_path=corpus_manifest,
            fixture_checksum=fixture_checksum,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"fixture coverage failed: {error}", file=sys.stderr)
        raise SystemExit(2) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vdb", description="Personal vector database")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="check local vector database connectivity")
    doctor.add_argument(
        "--offline", action="store_true", help="fail fast if the local model is not cached"
    )
    ingest = subparsers.add_parser("ingest", help="ingest a Markdown/TXT file")
    ingest.add_argument("path", type=Path)
    ingest_dir = subparsers.add_parser(
        "ingest-dir", help="ingest all supported files under a directory"
    )
    ingest_dir.add_argument("path", type=Path)
    delete = subparsers.add_parser("delete", help="delete all chunks for a document")
    delete.add_argument("document_id")
    reindex = subparsers.add_parser("reindex", help="replace a document's indexed chunks")
    reindex.add_argument("path", type=Path)
    reindex.add_argument("--document-id")
    backup = subparsers.add_parser("backup", help="create a Qdrant snapshot and manifest")
    backup.add_argument("--manifest", type=Path, default=Path("data/snapshots/latest.json"))
    backup.add_argument("--snapshot", type=Path, default=Path("data/snapshots/latest.tar.gz"))
    backup.add_argument("--corpus-manifest", type=Path)
    restore = subparsers.add_parser("restore", help="restore a Qdrant snapshot")
    restore.add_argument("location")
    restore.add_argument("--checksum")
    restore.add_argument("--manifest", type=Path)
    restore.add_argument("--corpus-manifest", type=Path)
    benchmark = subparsers.add_parser("benchmark", help="run the labeled retrieval benchmark")
    benchmark.add_argument(
        "--fixture", type=Path, default=Path("data/benchmarks/queries.json")
    )
    benchmark.add_argument("--limit", type=int, default=8)
    benchmark.add_argument("--min-score", type=float)
    benchmark.add_argument("--rerank", action="store_true")
    benchmark.add_argument("--repeat", type=int, default=1)
    benchmark.add_argument("--output", type=Path)
    benchmark.add_argument("--fixture-manifest", type=Path)
    benchmark.add_argument("--corpus-manifest", type=Path)
    benchmark.add_argument("--labels", type=Path)
    concurrency_probe = subparsers.add_parser(
        "concurrency-probe", help="run a bounded concurrent retrieval probe"
    )
    concurrency_probe.add_argument("--fixture", type=Path, required=True)
    concurrency_probe.add_argument("--concurrency", type=int, default=4)
    concurrency_probe.add_argument("--concurrency-levels", type=int, nargs="+")
    concurrency_probe.add_argument("--repetitions", type=int, default=1)
    concurrency_probe.add_argument("--limit", type=int, default=8)
    concurrency_probe.add_argument("--min-score", type=float)
    concurrency_probe.add_argument("--rerank", action="store_true")
    concurrency_probe.add_argument("--output", type=Path)
    concurrency_probe.add_argument("--fixture-manifest", type=Path)
    concurrency_probe.add_argument("--corpus-manifest", type=Path)
    concurrency_probe.add_argument("--labels", type=Path)
    fixture_validate = subparsers.add_parser(
        "fixture-validate", help="validate a labeled fixture against its acceptance manifest"
    )
    fixture_validate.add_argument("--fixture", type=Path, required=True)
    fixture_validate.add_argument("--manifest", type=Path, required=True)
    fixture_validate.add_argument("--corpus-manifest", type=Path)
    fixture_validate.add_argument("--labels", type=Path)
    fixture_coverage = subparsers.add_parser(
        "fixture-coverage", help="show fixture readiness counts without running retrieval"
    )
    fixture_coverage.add_argument("--fixture", type=Path, required=True)
    fixture_coverage.add_argument("--manifest", type=Path, required=True)
    fixture_coverage.add_argument("--labels", type=Path)
    fixture_coverage.add_argument("--corpus-manifest", type=Path)
    fixture_coverage.add_argument("--output", type=Path)
    fixture_label_template = subparsers.add_parser(
        "fixture-label-template",
        help="write a review-required label skeleton without source text",
    )
    fixture_label_template.add_argument("--fixture", type=Path, required=True)
    fixture_label_template.add_argument("--output", type=Path, required=True)
    fixture_label_template.add_argument(
        "--corpus-manifest", type=Path, required=True
    )
    fixture_merge = subparsers.add_parser(
        "fixture-merge", help="merge query or label shards with collision checks"
    )
    fixture_merge.add_argument(
        "kind", choices=("queries", "labels"), help="which shard format to merge"
    )
    fixture_merge.add_argument("--input", type=Path, nargs="+", required=True)
    fixture_merge.add_argument("--output", type=Path, required=True)
    corpus_inventory = subparsers.add_parser(
        "corpus-inventory", help="inventory supported local sources without source text"
    )
    corpus_inventory.add_argument("--root", type=Path)
    corpus_inventory.add_argument(
        "--output", type=Path, default=Path("data/derived/corpus-inventory.json")
    )
    corpus_inventory.add_argument(
        "--manifest", type=Path, default=Path("data/manifests/corpus-manifest.json")
    )
    search = subparsers.add_parser("search", help="search indexed chunks")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    search.add_argument("--min-score", type=float)
    search.add_argument("--rerank", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    _configure_utf8_output()
    args = build_parser().parse_args(argv)
    settings = (
        Settings(embedding_offline=True)
        if args.command == "doctor" and args.offline
        else Settings()
    )
    if args.command == "doctor":
        provider, store = _services(settings)
        try:
            provider.embed_query("health check")
            print("ok" if store.healthcheck() else "unavailable")
        finally:
            store.close()
        return
    if args.command == "delete":
        validate_document_id(args.document_id)
        store_type = {
            "dense": QdrantVectorStore,
            "hybrid": QdrantHybridVectorStore,
            "late": QdrantLateInteractionVectorStore,
            "quantized": QdrantQuantizedVectorStore,
        }[settings.retrieval_mode]
        store = store_type(settings.qdrant_url, _collection_name(settings))
        try:
            store.delete_document(args.document_id)
        finally:
            store.close()
        print(f"deleted document={args.document_id}")
        return
    if args.command == "fixture-validate":
        cases = _load_fixture_or_exit(args.fixture)
        summary = _validate_fixture_or_exit(
            cases,
            args.manifest,
            corpus_manifest=args.corpus_manifest,
            labels=args.labels,
        )
        print(summary)
        return
    if args.command == "fixture-coverage":
        cases = _load_fixture_or_exit(args.fixture)
        summary = _fixture_coverage_or_exit(
            cases,
            args.manifest,
            args.labels,
            args.corpus_manifest,
            "sha256:" + hashlib.sha256(args.fixture.read_bytes()).hexdigest(),
        )
        if args.output is not None:
            write_fixture_coverage_report(args.output, summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return
    if args.command == "fixture-label-template":
        cases = _load_fixture_or_exit(args.fixture)
        try:
            write_query_label_template(
                args.output, cases, corpus_manifest_path=args.corpus_manifest
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            print(f"fixture label template failed: {error}", file=sys.stderr)
            raise SystemExit(2) from None
        print(f"fixture label template={args.output} review_required=true")
        return
    if args.command == "fixture-merge":
        try:
            summary = (
                merge_query_fixture_files(args.input, args.output)
                if args.kind == "queries"
                else merge_query_label_files(args.input, args.output)
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            print(f"fixture merge failed: {error}", file=sys.stderr)
            raise SystemExit(2) from None
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return
    if args.command == "corpus-inventory":
        root = args.root or settings.data_dir / "sources"
        excluded_count = count_excluded_files(root)
        unsupported_suffixes = summarize_unsupported_files(root)
        try:
            records = write_corpus_inventory(
                root,
                args.output,
                max_source_bytes=settings.source_max_bytes,
                max_files=settings.source_max_files,
                max_total_bytes=settings.source_max_total_bytes,
            )
        except (OSError, ValueError, TypeError) as error:
            print(f"corpus inventory failed: {error}", file=sys.stderr)
            raise SystemExit(2) from None
        manifest = write_corpus_manifest(root, records, args.manifest)
        parsed_count = sum(record.get("status") == "parsed" for record in records)
        failed_count = sum(record.get("status") == "failed" for record in records)
        duplicate_count = sum(
            record.get("duplicate_of") is not None for record in records
        )
        format_counts = Counter(str(record["suffix"]) for record in records)
        failure_types = Counter(
            str(record["error_type"])
            for record in records
            if record.get("status") == "failed" and record.get("error_type")
        )
        format_summary = ",".join(
            f"{suffix}:{format_counts[suffix]}" for suffix in sorted(format_counts)
        ) or "none"
        failure_summary = ",".join(
            f"{error_type}:{failure_types[error_type]}"
            for error_type in sorted(failure_types)
        ) or "none"
        unsupported_summary = ",".join(
            f"{suffix}:{count}" for suffix, count in unsupported_suffixes.items()
        ) or "none"
        print(
            f"inventory_sources={len(records)} "
            f"excluded_files={excluded_count} "
            f"unsupported_files={sum(unsupported_suffixes.values())} "
            f"unsupported_suffixes={unsupported_summary} "
            f"parsed_sources={parsed_count} "
            f"failed_sources={failed_count} "
            f"duplicate_sources={duplicate_count} "
            f"chunks={manifest['total_chunks']} "
            f"extracted_chars={manifest['total_extracted_chars']} "
            f"formats={format_summary} "
            f"failure_types={failure_summary} "
            f"corpus_checksum={manifest['corpus_checksum']} "
            f"output={args.output} manifest={args.manifest}"
        )
        return
    if args.command in {"benchmark", "concurrency-probe"} and args.fixture_manifest:
        preflight_cases = _load_fixture_or_exit(args.fixture)
        _validate_fixture_or_exit(
            preflight_cases,
            args.fixture_manifest,
            corpus_manifest=args.corpus_manifest,
            labels=args.labels,
        )
        print("fixture preflight=passed")
    backup_corpus_parser_versions = None
    backup_corpus_checksum = None
    if args.command == "backup" and args.corpus_manifest is not None:
        backup_corpus_manifest = read_corpus_manifest(args.corpus_manifest)
        backup_corpus_parser_versions = backup_corpus_manifest["parser_versions"]
        backup_corpus_checksum = backup_corpus_manifest["corpus_checksum"]
    provider, store = _services(settings)
    try:
        if args.command == "backup":
            snapshot_name = store.create_snapshot(args.snapshot)
            write_backup_manifest(
                args.manifest,
                collection_name=_collection_name(settings),
                snapshot_name=snapshot_name,
                snapshot_checksum=getattr(store, "last_snapshot_checksum", None),
                parser_versions=backup_corpus_parser_versions,
                corpus_checksum=backup_corpus_checksum,
                embedding=provider.manifest,
            )
            print(f"backup snapshot={snapshot_name} manifest={args.manifest}")
            return
        if args.command == "restore":
            checksum = args.checksum
            if args.manifest is not None:
                manifest = read_backup_manifest(args.manifest)
                if manifest.collection_name != _collection_name(settings):
                    raise ValueError("backup collection does not match configured collection")
                if manifest.embedding_manifest_id != provider.manifest.manifest_id:
                    raise ValueError("backup embedding manifest does not match active provider")
                if args.corpus_manifest is not None:
                    corpus_manifest = read_corpus_manifest(args.corpus_manifest)
                    if (
                        manifest.corpus_checksum is not None
                        and manifest.corpus_checksum != corpus_manifest["corpus_checksum"]
                    ):
                        raise ValueError("backup corpus checksum does not match corpus manifest")
                if (
                    manifest.dimension != provider.manifest.dimension
                    or manifest.metric != provider.manifest.metric
                ):
                    raise ValueError("backup vector contract does not match active provider")
                if Path(args.location).name != Path(manifest.snapshot_name).name:
                    raise ValueError("restore snapshot does not match backup manifest")
                if checksum is not None and manifest.snapshot_checksum not in (None, checksum):
                    raise ValueError("restore checksum does not match backup manifest")
                checksum = checksum or manifest.snapshot_checksum
            restored = store.restore_snapshot(args.location, checksum=checksum)
            print("restored" if restored else "restore-failed")
            return
        if args.command == "benchmark":
            cases = _load_fixture_or_exit(args.fixture)
            service = RetrievalService(
                provider,
                store,
                _reranker(settings),
                _planner(settings),
                default_min_score=settings.retrieval_min_score,
            )
            fixture_checksum = "sha256:" + hashlib.sha256(args.fixture.read_bytes()).hexdigest()
            corpus_checksum = None
            if args.corpus_manifest is not None:
                corpus_checksum = read_corpus_manifest(args.corpus_manifest)["corpus_checksum"]
            elif args.fixture_manifest is not None:
                fixture_manifest = json.loads(
                    args.fixture_manifest.read_text(encoding="utf-8")
                )
                corpus_checksum = fixture_manifest.get("corpus_checksum")

            class BenchmarkSearcher:
                def search(self, query: str, *, limit: int = 8, filters=None):
                    return service.search(
                        query,
                        limit=limit,
                        min_score=args.min_score,
                        rerank=args.rerank,
                        filters=filters,
                    )

            results = run_repeated_benchmark(
                cases,
                BenchmarkSearcher(),
                k=args.limit,
                repeats=args.repeat,
                fixture_checksum=fixture_checksum,
                corpus_checksum=corpus_checksum,
                embedding_manifest_id=getattr(
                    getattr(provider, "manifest", None), "manifest_id", None
                ),
            )
            if args.output is not None:
                if len(results) == 1:
                    write_benchmark_result(args.output, results[0])
                else:
                    write_benchmark_results(args.output, results)
            for repeat_index, result in enumerate(results, start=1):
                prefix = f"repeat={repeat_index} " if len(results) > 1 else ""
                print(
                    f"{prefix}mode={settings.retrieval_mode} queries={result.query_count} "
                    f"recall_at_k={result.recall_at_k:.4f} "
                    f"elapsed_seconds={result.elapsed_seconds:.4f} "
                    f"cpu_seconds={result.cpu_seconds:.6f} "
                    f"rss_mb={result.rss_mb if result.rss_mb is not None else 'n/a'} "
                    f"mrr_at_k={result.mrr_at_k:.4f} ndcg_at_k={result.ndcg_at_k:.4f} "
                    f"negative_success_rate={result.negative_success_rate:.4f} "
                    f"p50_ms={result.latency_p50_ms:.3f} p95_ms={result.latency_p95_ms:.3f} "
                    f"p99_ms={result.latency_p99_ms:.3f} error_rate={result.error_rate:.4f}"
                )
            if len(results) > 1:
                summary = summarize_benchmark_results(results)
                means = summary["metrics"]
                print(
                    "summary="
                    f"runs={summary['run_count']} "
                    f"recall_mean={means['recall_at_k']['mean']:.4f} "
                    f"mrr_mean={means['mrr_at_k']['mean']:.4f} "
                    f"ndcg_mean={means['ndcg_at_k']['mean']:.4f} "
                    f"p95_mean_ms={means['latency_p95_ms']['mean']:.3f} "
                    f"error_mean={means['error_rate']['mean']:.4f}"
                )
            return
        if args.command == "concurrency-probe":
            cases = _load_fixture_or_exit(args.fixture)
            service = RetrievalService(
                provider,
                store,
                _reranker(settings),
                _planner(settings),
                default_min_score=settings.retrieval_min_score,
            )
            fixture_checksum = "sha256:" + hashlib.sha256(args.fixture.read_bytes()).hexdigest()
            corpus_checksum = None
            if args.corpus_manifest is not None:
                corpus_checksum = read_corpus_manifest(args.corpus_manifest)["corpus_checksum"]
            elif args.fixture_manifest is not None:
                fixture_manifest = json.loads(
                    args.fixture_manifest.read_text(encoding="utf-8")
                )
                corpus_checksum = fixture_manifest.get("corpus_checksum")

            class ProbeSearcher:
                def search(self, query: str, *, limit: int = 8, filters=None):
                    return service.search(
                        query,
                        limit=limit,
                        min_score=args.min_score,
                        rerank=args.rerank,
                        filters=filters,
                    )

            if args.concurrency_levels is not None:
                results = run_concurrency_matrix(
                    cases,
                    ProbeSearcher(),
                    args.concurrency_levels,
                    k=args.limit,
                    repetitions=args.repetitions,
                    fixture_checksum=fixture_checksum,
                    corpus_checksum=corpus_checksum,
                    embedding_manifest_id=getattr(
                        getattr(provider, "manifest", None), "manifest_id", None
                    ),
                )
                encoded = {"runs": [result.to_dict() for result in results]}
                if args.output is not None:
                    write_concurrency_matrix_results(args.output, results)
            else:
                result = run_concurrency_probe(
                    cases,
                    ProbeSearcher(),
                    k=args.limit,
                    concurrency=args.concurrency,
                    repetitions=args.repetitions,
                    fixture_checksum=fixture_checksum,
                    corpus_checksum=corpus_checksum,
                    embedding_manifest_id=getattr(
                        getattr(provider, "manifest", None), "manifest_id", None
                    ),
                )
                encoded = result.to_dict()
            if args.output is not None and args.concurrency_levels is None:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps(encoded, indent=2), encoding="utf-8"
                )
            print(json.dumps(encoded, ensure_ascii=False, sort_keys=True))
            return
        if args.command == "ingest":
            result = IngestService(
                provider,
                store,
                source_root=settings.data_dir / "sources",
                max_source_bytes=settings.source_max_bytes,
                max_directory_files=settings.source_max_files,
                max_directory_bytes=settings.source_max_total_bytes,
            ).ingest_file(args.path)
            print(f"indexed document={result.document_id} chunks={result.chunk_count}")
            return
        if args.command == "ingest-dir":
            result = IngestService(
                provider,
                store,
                source_root=settings.data_dir / "sources",
                max_source_bytes=settings.source_max_bytes,
                max_directory_files=settings.source_max_files,
                max_directory_bytes=settings.source_max_total_bytes,
            ).ingest_directory(args.path)
            print(
                f"indexed_documents={len(result.indexed)} "
                f"failed_documents={len(result.failures)}"
            )
            return
        if args.command == "reindex":
            result = IngestService(
                provider,
                store,
                source_root=settings.data_dir / "sources",
                max_source_bytes=settings.source_max_bytes,
                max_directory_files=settings.source_max_files,
                max_directory_bytes=settings.source_max_total_bytes,
            ).reindex_file(args.path, args.document_id)
            print(f"reindexed document={result.document_id} chunks={result.chunk_count}")
            return
        if args.command == "search":
            results = RetrievalService(
                provider,
                store,
                _reranker(settings),
                _planner(settings),
                default_min_score=settings.retrieval_min_score,
            ).search(
                args.query, limit=args.limit, min_score=args.min_score, rerank=args.rerank
            )
            for result in results:
                print(f"{result.score:.4f}\t{result.document_id}\t{result.source_uri}\t{result.text}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
