from uuid import uuid4

from qdrant_client.http import models

from personal_vector_db.contracts import EmbeddingManifest
from personal_vector_db.embeddings import SparseLexicalEncoder
from personal_vector_db.retrieval import RetrievalFilter, RetrievalService
from personal_vector_db.storage import QdrantHybridVectorStore


class FakeProvider:
    manifest = EmbeddingManifest("test", "model", "r1", 3, "cosine", True)

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def hybrid_point(store: QdrantHybridVectorStore, text: str, title: str) -> models.PointStruct:
    return models.PointStruct(
        id=str(uuid4()),
        vector=store.prepare_vector([1.0, 0.0, 0.0], text),
        payload={
            "document_id": f"doc_{title.lower()}",
            "chunk_id": f"chunk_{title.lower()}",
            "text": text,
            "source_uri": "file:///notes.md",
            "title": title,
            "location": {"start_line": 1},
            "embedding_manifest_id": FakeProvider.manifest.manifest_id,
            "owner_id": "me",
            "document_status": "active",
        },
    )


def test_sparse_encoder_is_deterministic_and_non_empty() -> None:
    encoder = SparseLexicalEncoder()

    first = encoder.encode("Türkçe hybrid arama")
    second = encoder.encode("Türkçe hybrid arama")

    assert first == second
    assert first.indices
    assert len(first.indices) == len(first.values)


def test_hybrid_qdrant_round_trip_preserves_provenance_and_stage() -> None:
    store = QdrantHybridVectorStore(":memory:", "hybrid_test")
    store.ensure_collection(3)
    store.upsert(
        [
            hybrid_point(store, "RRF exact identifier alpha", "Alpha"),
            hybrid_point(store, "semantic project planning", "Beta"),
        ]
    )

    results = RetrievalService(FakeProvider(), store).search(
        "alpha", limit=1, filters=RetrievalFilter(titles=("Alpha",))
    )

    assert len(results) == 1
    assert results[0].title == "Alpha"
    assert results[0].source_uri == "file:///notes.md"
    assert results[0].retrieval_stage == "hybrid"
