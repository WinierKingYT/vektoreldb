from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from qdrant_client.http import models

from personal_vector_db.api import SearchResponse, create_app
from personal_vector_db.contracts import EmbeddingManifest
from personal_vector_db.ingest import IngestService
from personal_vector_db.retrieval import ExactVectorStore, RetrievalService


class FakeProvider:
    manifest = EmbeddingManifest("test", "model", "r1", 3, "cosine", True)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def point(point_id: str, vector: list[float], document_id: str, text: str) -> models.PointStruct:
    return models.PointStruct(
        id=point_id,
        vector=vector,
        payload={
            "document_id": document_id,
            "chunk_id": f"{document_id}_chunk_1",
            "text": text,
            "source_uri": "file:///notes.md",
            "title": "Notes",
            "location": {"start_line": 1},
            "embedding_manifest_id": "test:model@r1",
            "parser_version": "markdown-v1",
            "document_status": "active",
            "security_flags": [],
        },
    )


def test_search_api_returns_provenance_for_rag() -> None:
    store = ExactVectorStore()
    store.upsert([point("1", [1.0, 0.0, 0.0], "doc_a", "bir içerik")])
    app = create_app(RetrievalService(FakeProvider(), store))

    response = TestClient(app).post("/v1/search", json={"query": "bir soru"})

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["document_id"] == "doc_a"
    assert body["results"][0]["source_uri"] == "file:///notes.md"
    assert body["results"][0]["parser_version"] == "markdown-v1"
    assert body["results"][0]["heading_path"] == []
    assert body["results"][0]["document_status"] == "active"
    assert body["results"][0]["security_flags"] == []


def test_search_api_accepts_metadata_filters() -> None:
    store = ExactVectorStore()
    first = point("first", [1.0, 0.0, 0.0], "doc_first", "ilk")
    second = point("second", [1.0, 0.0, 0.0], "doc_second", "ikinci")
    second.payload["title"] = "Target"
    store.upsert([first, second])
    client = TestClient(create_app(RetrievalService(FakeProvider(), store)))

    response = client.post("/v1/search", json={"query": "soru", "titles": ["Target"]})

    assert response.status_code == 200
    assert [hit["document_id"] for hit in response.json()["results"]] == ["doc_second"]


def test_search_api_exposes_abstention_diagnostics() -> None:
    service = RetrievalService(FakeProvider(), ExactVectorStore(), default_min_score=0.5)

    response = TestClient(create_app(service)).post("/v1/search", json={"query": "soru"})

    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["abstention_reason"] == "no_candidates"
    assert response.json()["candidate_count"] == 0
    assert response.json()["threshold_rejected_count"] == 0

    service.store.upsert([point("low", [-1.0, 0.0, 0.0], "doc_low", "düşük skor")])
    response = TestClient(create_app(service)).post("/v1/search", json={"query": "soru"})

    assert response.json()["results"] == []
    assert response.json()["abstention_reason"] == "below_min_score"
    assert response.json()["candidate_count"] == 1
    assert response.json()["threshold_rejected_count"] == 1


def test_search_response_rejects_unknown_abstention_reason() -> None:
    with pytest.raises(ValueError):
        SearchResponse(query="soru", results=[], abstention_reason="unknown")


def test_health_api_reflects_store_status() -> None:
    service = RetrievalService(FakeProvider(), ExactVectorStore())

    response = TestClient(create_app(service)).get("/v1/health")

    assert response.json() == {"status": "ok"}


def test_api_rejects_ingest_service_without_source_root() -> None:
    provider = FakeProvider()
    store = ExactVectorStore()

    with pytest.raises(ValueError, match="source_root"):
        create_app(RetrievalService(provider, store), IngestService(provider, store))


def test_api_lifespan_closes_storage() -> None:
    class ClosableStore(ExactVectorStore):
        def __init__(self) -> None:
            super().__init__()
            self.closed = False

        def close(self) -> None:
            self.closed = True

    store = ClosableStore()
    app = create_app(RetrievalService(FakeProvider(), store))

    with TestClient(app):
        assert not store.closed

    assert store.closed


def test_search_api_rejects_empty_query() -> None:
    service = RetrievalService(FakeProvider(), ExactVectorStore())

    response = TestClient(create_app(service)).post("/v1/search", json={"query": ""})

    assert response.status_code == 422
    assert set(response.json()) == {"code", "message", "retryable", "request_id", "details"}
    assert response.json()["code"] == "validation_error"


def test_search_api_rejects_oversized_query() -> None:
    service = RetrievalService(FakeProvider(), ExactVectorStore())

    response = TestClient(create_app(service)).post(
        "/v1/search", json={"query": "x" * 4_001}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_search_api_requires_configured_reranker() -> None:
    service = RetrievalService(FakeProvider(), ExactVectorStore())

    response = TestClient(create_app(service)).post(
        "/v1/search", json={"query": "soru", "rerank": True}
    )

    assert response.status_code == 400
    assert response.json()["code"] == "request_error"


def test_search_api_rejects_out_of_range_min_score() -> None:
    service = RetrievalService(FakeProvider(), ExactVectorStore())

    response = TestClient(create_app(service)).post(
        "/v1/search", json={"query": "soru", "min_score": 1.1}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_ingest_api_rejects_unsupported_v1_fields(tmp_path: Path) -> None:
    provider = FakeProvider()
    store = ExactVectorStore()
    ingest = IngestService(provider, store, source_root=tmp_path)
    app = create_app(RetrievalService(provider, store), ingest)

    response = TestClient(app).post(
        "/v1/documents:ingest", json={"file_ref": "note.md", "content": "gizli"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_api_redacts_unexpected_storage_errors() -> None:
    class BrokenStore(ExactVectorStore):
        def search(self, vector, limit=10):
            raise RuntimeError("secret backend connection details")

    service = RetrievalService(FakeProvider(), BrokenStore())
    client = TestClient(create_app(service), raise_server_exceptions=False)

    response = client.post("/v1/search", json={"query": "test"})

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "secret backend" not in response.text


def test_api_returns_safe_error_envelope_for_invalid_source(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    provider = FakeProvider()
    store = ExactVectorStore()
    ingest = IngestService(provider, store, source_root=source_root)
    client = TestClient(create_app(RetrievalService(provider, store), ingest))

    response = client.post("/v1/documents:ingest", json={"file_ref": "C:/private/secret.pdf"})

    assert response.status_code == 400
    assert response.json()["code"] == "request_error"
    assert "secret.pdf" not in response.text


def test_api_redacts_filesystem_path_from_ingest_errors(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    provider = FakeProvider()
    store = ExactVectorStore()
    ingest = IngestService(provider, store, source_root=source_root)
    client = TestClient(create_app(RetrievalService(provider, store), ingest))
    missing = source_root / "private-name.md"

    response = client.post("/v1/documents:ingest", json={"file_ref": str(missing)})

    assert response.status_code == 400
    assert "private-name.md" not in response.text
    assert response.json()["message"] == "ingest request could not be processed"


def test_document_lifecycle_api_ingests_and_deletes(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    path = source_root / "note.md"
    path.write_text("# Not\n\nİçerik.", encoding="utf-8")
    provider = FakeProvider()
    store = ExactVectorStore()
    ingest = IngestService(provider, store, source_root=source_root)
    client = TestClient(create_app(RetrievalService(provider, store), ingest))

    response = client.post("/v1/documents:ingest", json={"file_ref": str(path)})
    document_id = response.json()["document_id"]
    deleted = client.delete(f"/v1/documents/{document_id}")

    assert response.status_code == 202
    assert response.json()["status"] == "indexed"
    assert deleted.status_code == 202
    assert deleted.json()["status"] == "deleted"


def test_document_lifecycle_api_reindexes(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    path = source_root / "note.md"
    path.write_text("Eski içerik.", encoding="utf-8")
    provider = FakeProvider()
    store = ExactVectorStore()
    ingest = IngestService(provider, store, source_root=source_root)
    client = TestClient(create_app(RetrievalService(provider, store), ingest))

    first = client.post("/v1/documents:ingest", json={"file_ref": str(path)})
    document_id = first.json()["document_id"]
    path.write_text("Yeni içerik.", encoding="utf-8")
    reindexed = client.post(
        f"/v1/documents/{document_id}:reindex", json={"file_ref": str(path)}
    )

    assert reindexed.status_code == 202
    assert reindexed.json()["document_id"] == document_id
    assert len(store._points) == 1
    assert store._points[0][1].payload["text"] == "Yeni içerik."
