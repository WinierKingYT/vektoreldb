import json
from types import SimpleNamespace

import pytest

import personal_vector_db.cli as cli
from personal_vector_db.backup import write_backup_manifest
from personal_vector_db.cli import build_parser
from personal_vector_db.config import Settings
from personal_vector_db.contracts import EmbeddingManifest
from personal_vector_db.corpus import write_corpus_manifest


def test_cli_parser_supports_core_commands() -> None:
    assert build_parser().parse_args(["doctor"]).command == "doctor"
    assert build_parser().parse_args(["doctor", "--offline"]).offline is True
    assert build_parser().parse_args(["ingest", "notes.md"]).path.name == "notes.md"
    search_args = build_parser().parse_args(
        ["search", "bir soru", "--limit", "3", "--min-score", "0.7"]
    )
    assert search_args.limit == 3
    assert search_args.min_score == 0.7
    assert build_parser().parse_args(["delete", "doc_abc"]).document_id == "doc_abc"
    assert (
        build_parser()
        .parse_args(["reindex", "notes.md", "--document-id", "doc_abc"])
        .document_id
        == "doc_abc"
    )
    assert build_parser().parse_args(["backup"]).command == "backup"
    assert build_parser().parse_args(["restore", "file:///snapshot"]).location == "file:///snapshot"
    assert build_parser().parse_args(
        ["restore", "file:///snapshot", "--corpus-manifest", "corpus.json"]
    ).corpus_manifest.name == "corpus.json"
    assert build_parser().parse_args(
        ["restore", "file:///snapshot", "--manifest", "manifest.json"]
    ).manifest.name == "manifest.json"
    benchmark_args = build_parser().parse_args(
        ["benchmark", "--limit", "5", "--min-score", "0.8", "--rerank"]
    )
    assert benchmark_args.limit == 5
    assert benchmark_args.min_score == 0.8
    assert benchmark_args.rerank is True
    assert benchmark_args.repeat == 1
    matrix_args = build_parser().parse_args(
        ["concurrency-probe", "--fixture", "q.json", "--concurrency-levels", "1", "2", "4"]
    )
    assert matrix_args.concurrency_levels == [1, 2, 4]
    coverage_args = build_parser().parse_args(
        [
            "fixture-coverage",
            "--fixture",
            "q.json",
            "--manifest",
            "m.json",
            "--corpus-manifest",
            "corpus.json",
        ]
    )
    assert coverage_args.command == "fixture-coverage"
    assert coverage_args.corpus_manifest.name == "corpus.json"
    assert coverage_args.output is None
    inventory_args = build_parser().parse_args(["corpus-inventory"])
    assert inventory_args.output.as_posix() == "data/derived/corpus-inventory.json"
    assert inventory_args.manifest.as_posix() == "data/manifests/corpus-manifest.json"


def test_cli_configures_utf8_output(monkeypatch) -> None:
    calls: list[dict[str, str]] = []

    class Stream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

        def write(self, _text):
            return 0

        def flush(self):
            pass

    monkeypatch.setattr(cli.sys, "stdout", Stream())
    monkeypatch.setattr(cli.sys, "stderr", Stream())
    monkeypatch.setattr(cli, "Settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(cli, "_services", lambda _settings: (
        type("Provider", (), {"embed_query": lambda self, text: [1.0]})(),
        type("Store", (), {"healthcheck": lambda self: True, "close": lambda self: None})(),
    ))

    cli.main(["doctor"])

    assert calls == [
        {"encoding": "utf-8", "errors": "replace"},
        {"encoding": "utf-8", "errors": "replace"},
    ]


def test_fixture_validation_reports_contract_errors_without_traceback(capsys) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "fixture-validate",
                "--fixture",
                "data/benchmarks/queries.json",
                "--manifest",
                "data/benchmarks/query-fixture-manifest.json",
            ]
        )

    assert error.value.code == 2
    assert capsys.readouterr().err.startswith("fixture validation failed:")


def test_fixture_loading_reports_malformed_json_without_traceback(tmp_path, capsys) -> None:
    fixture = tmp_path / "broken.json"
    fixture.write_text("{not-json", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "fixture-validate",
                "--fixture",
                str(fixture),
                "--manifest",
                "data/benchmarks/query-fixture-manifest.json",
            ]
        )

    assert error.value.code == 2
    assert capsys.readouterr().err.startswith("fixture loading failed:")


def test_ingest_does_not_open_a_second_qdrant_client(monkeypatch, capsys) -> None:
    class FailingStore:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("CLI opened an extra Qdrant client")

    class FakeProvider:
        manifest = type("Manifest", (), {"manifest_id": "test-manifest"})()

    class FakeIngest:
        def __init__(
            self,
            provider,
            store,
            *,
            source_root,
            max_source_bytes,
            max_directory_files,
            max_directory_bytes,
        ):
            assert provider is fake_provider
            assert store is fake_store
            assert source_root.name == "sources"
            assert max_source_bytes == 10_000_000
            assert max_directory_files == 5_000
            assert max_directory_bytes == 1_000_000_000

        def ingest_file(self, path):
            assert path.name == "notes.md"
            return type("Result", (), {
                "document_id": "doc_test",
                "chunk_count": 1,
                "embedding_manifest_id": "test-manifest",
            })()

    fake_provider = FakeProvider()
    class FakeStore:
        def close(self):
            pass

    fake_store = FakeStore()
    monkeypatch.setattr(cli, "QdrantVectorStore", FailingStore)
    monkeypatch.setattr(cli, "_services", lambda _settings: (fake_provider, fake_store))
    monkeypatch.setattr(cli, "IngestService", FakeIngest)

    cli.main(["ingest", "notes.md"])

    assert "indexed document=doc_test chunks=1" in capsys.readouterr().out


def test_unsupported_embedding_provider_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported embedding provider"):
        cli._services(Settings(embedding_provider="remote", _env_file=None))


def test_cli_delete_rejects_malformed_document_id_before_opening_store(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "QdrantVectorStore",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("store must not open for an invalid document id")
        ),
    )

    with pytest.raises(ValueError, match="invalid document_id"):
        cli.main(["delete", "doc_../outside"])


def test_doctor_fails_closed_for_unsupported_runtime_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "Settings",
        lambda: Settings(distance_metric="dot", _env_file=None),
    )

    with pytest.raises(ValueError, match="unsupported distance metric"):
        cli.main(["doctor"])


def test_doctor_checks_embedding_provider_and_storage(monkeypatch, capsys) -> None:
    calls: list[str] = []

    class FakeProvider:
        manifest = type("Manifest", (), {"dimension": 3})()

        def embed_query(self, text: str) -> list[float]:
            calls.append(text)
            return [1.0, 0.0, 0.0]

    class FakeStore:
        def ensure_collection(self, dimension: int) -> None:
            assert dimension == 3

        def healthcheck(self) -> bool:
            return True

        def close(self) -> None:
            calls.append("closed")

    monkeypatch.setattr(cli, "_services", lambda _settings: (FakeProvider(), FakeStore()))

    cli.main(["doctor"])

    assert calls == ["health check", "closed"]
    assert capsys.readouterr().out.strip() == "ok"


def test_restore_rejects_manifest_for_another_collection(monkeypatch, tmp_path) -> None:
    embedding = EmbeddingManifest("local", "model", "r1", 3, "cosine", True)
    manifest_path = tmp_path / "backup.json"
    write_backup_manifest(
        manifest_path,
        collection_name="other_collection",
        snapshot_name="snapshot-1",
        embedding=embedding,
    )

    class FakeProvider:
        manifest = embedding

    class FakeStore:
        def close(self) -> None:
            pass

        def restore_snapshot(self, location, *, checksum=None):
            raise AssertionError("restore must not start for an incompatible manifest")

    monkeypatch.setattr(
        cli,
        "Settings",
        lambda: Settings(collection_name="configured_collection", _env_file=None),
    )
    monkeypatch.setattr(cli, "_services", lambda _settings: (FakeProvider(), FakeStore()))

    with pytest.raises(ValueError, match="collection"):
        cli.main(["restore", "snapshot-1", "--manifest", str(manifest_path)])


def test_restore_rejects_snapshot_name_mismatch(monkeypatch, tmp_path) -> None:
    embedding = EmbeddingManifest("local", "model", "r1", 3, "cosine", True)
    manifest_path = tmp_path / "backup.json"
    write_backup_manifest(
        manifest_path,
        collection_name="configured_collection",
        snapshot_name="expected-snapshot",
        embedding=embedding,
    )

    class FakeProvider:
        manifest = embedding

    class FakeStore:
        def close(self) -> None:
            pass

        def restore_snapshot(self, location, *, checksum=None):
            raise AssertionError("restore must not start for a mismatched snapshot")

    monkeypatch.setattr(
        cli,
        "Settings",
        lambda: Settings(collection_name="configured_collection", _env_file=None),
    )
    monkeypatch.setattr(cli, "_services", lambda _settings: (FakeProvider(), FakeStore()))

    with pytest.raises(ValueError, match="snapshot"):
        cli.main(["restore", "wrong-snapshot", "--manifest", str(manifest_path)])


def test_restore_rejects_different_corpus_manifest(monkeypatch, tmp_path) -> None:
    embedding = EmbeddingManifest("local", "model", "r1", 3, "cosine", True)
    backup_path = tmp_path / "backup.json"
    write_backup_manifest(
        backup_path,
        collection_name="configured_collection",
        snapshot_name="snapshot-1",
        corpus_checksum="sha256:" + "a" * 64,
        embedding=embedding,
    )
    corpus_root = tmp_path / "sources"
    corpus_root.mkdir()
    corpus_manifest_path = tmp_path / "corpus.json"
    write_corpus_manifest(corpus_root, [], corpus_manifest_path)

    class FakeProvider:
        manifest = embedding

    class FakeStore:
        def close(self) -> None:
            pass

        def restore_snapshot(self, location, *, checksum=None):
            raise AssertionError("restore must not start for a different corpus")

    monkeypatch.setattr(
        cli,
        "Settings",
        lambda: Settings(collection_name="configured_collection", _env_file=None),
    )
    monkeypatch.setattr(cli, "_services", lambda _settings: (FakeProvider(), FakeStore()))

    with pytest.raises(ValueError, match="corpus checksum"):
        cli.main(
            [
                "restore",
                "snapshot-1",
                "--manifest",
                str(backup_path),
                "--corpus-manifest",
                str(corpus_manifest_path),
            ]
        )


def test_backup_rejects_invalid_corpus_before_opening_services(monkeypatch, tmp_path) -> None:
    manifest_path = tmp_path / "broken-corpus.json"
    manifest_path.write_text("{not-json", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "_services",
        lambda _settings: (_ for _ in ()).throw(
            AssertionError("services must not open for an invalid corpus manifest")
        ),
    )

    with pytest.raises(ValueError, match="could not be read"):
        cli.main(["backup", "--corpus-manifest", str(manifest_path)])


def test_corpus_inventory_cli_prints_privacy_safe_quality_summary(tmp_path, capsys) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "one.md").write_text("# One\n\ncontent", encoding="utf-8")
    output = tmp_path / "inventory.json"
    manifest = tmp_path / "corpus.json"

    cli.main(
        [
            "corpus-inventory",
            "--root",
            str(root),
            "--output",
            str(output),
            "--manifest",
            str(manifest),
        ]
    )

    message = capsys.readouterr().out
    assert "inventory_sources=1" in message
    assert "excluded_files=0" in message
    assert "unsupported_files=0" in message
    assert "unsupported_suffixes=none" in message
    assert "parsed_sources=1" in message
    assert "failed_sources=0" in message
    assert "duplicate_sources=0" in message
    assert "chunks=1" in message
    assert "extracted_chars=7" in message
    assert "formats=.md:1" in message
    assert "failure_types=none" in message


def test_corpus_inventory_cli_rejects_over_budget_before_writing(
    tmp_path, monkeypatch, capsys
) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "one.md").write_text("one", encoding="utf-8")
    (root / "two.md").write_text("two", encoding="utf-8")
    output = tmp_path / "inventory.json"
    manifest = tmp_path / "corpus.json"
    monkeypatch.setenv("VDB_SOURCE_MAX_FILES", "1")

    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "corpus-inventory",
                "--root",
                str(root),
                "--output",
                str(output),
                "--manifest",
                str(manifest),
            ]
        )

    assert error.value.code == 2
    assert "corpus inventory failed" in capsys.readouterr().err
    assert not output.exists()
    assert not manifest.exists()


def test_fixture_coverage_cli_writes_privacy_safe_report(tmp_path, capsys) -> None:
    fixture = tmp_path / "queries.json"
    fixture.write_text(
        '[{"query_id":"q1","text":"gizli-sorgu-123","relevant_chunk_ids":[]}]',
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
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
                "notes": "test",
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "coverage.json"

    cli.main(
        [
            "fixture-coverage",
            "--fixture",
            str(fixture),
            "--manifest",
            str(manifest),
            "--output",
            str(output),
        ]
    )

    assert output.exists()
    assert "gizli-sorgu-123" not in output.read_text(encoding="utf-8")
    assert json.loads(output.read_text(encoding="utf-8"))["query_count"] == 1
    assert json.loads(output.read_text(encoding="utf-8"))["fixture_checksum"].startswith("sha256:")
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["parser_versions_binding_status"] == "not-provided"
    assert json.loads(capsys.readouterr().out)["query_count"] == 1


def test_concurrency_probe_cli_prints_machine_readable_json(tmp_path, monkeypatch, capsys) -> None:
    fixture = tmp_path / "queries.json"
    fixture.write_text(
        '[{"query_id":"q1","text":"soru","relevant_chunk_ids":[]}]',
        encoding="utf-8",
    )

    class Store:
        def close(self) -> None:
            return None

    monkeypatch.setattr(cli, "_services", lambda _settings: (object(), Store()))
    monkeypatch.setattr(cli, "RetrievalService", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        cli,
        "run_concurrency_probe",
        lambda *_args, **_kwargs: SimpleNamespace(
            to_dict=lambda: {
                "concurrency": 1,
                "total_requests": 1,
                "successful_requests": 1,
                "error_count": 0,
            }
        ),
    )

    cli.main(["concurrency-probe", "--fixture", str(fixture)])

    output = capsys.readouterr().out.strip()
    assert json.loads(output)["successful_requests"] == 1


def test_concurrency_probe_cli_prints_matrix_json(tmp_path, monkeypatch, capsys) -> None:
    fixture = tmp_path / "queries.json"
    fixture.write_text(
        '[{"query_id":"q1","text":"soru","relevant_chunk_ids":[]}]',
        encoding="utf-8",
    )

    class Store:
        def close(self) -> None:
            return None

    monkeypatch.setattr(cli, "_services", lambda _settings: (object(), Store()))
    monkeypatch.setattr(cli, "RetrievalService", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        cli,
        "run_concurrency_matrix",
        lambda *_args, **_kwargs: [
            SimpleNamespace(to_dict=lambda: {"concurrency": 1}),
            SimpleNamespace(to_dict=lambda: {"concurrency": 2}),
        ],
    )

    cli.main(
        [
            "concurrency-probe",
            "--fixture",
            str(fixture),
            "--concurrency-levels",
            "1",
            "2",
        ]
    )

    output = json.loads(capsys.readouterr().out.strip())
    assert [run["concurrency"] for run in output["runs"]] == [1, 2]
