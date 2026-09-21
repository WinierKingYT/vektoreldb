from uuid import uuid4

from qdrant_client.http import models

from personal_vector_db.contracts import EmbeddingManifest
from personal_vector_db.embeddings import LateInteractionEncoder
from personal_vector_db.retrieval import RetrievalService
from personal_vector_db.storage import QdrantLateInteractionVectorStore


class FakeProvider:
    manifest = EmbeddingManifest("test", "model", "r1", 3, "cosine", True)

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def test_late_encoder_is_bounded_and_deterministic() -> None:
    encoder = LateInteractionEncoder()

    first = encoder.encode("Türkçe late interaction")
    second = encoder.encode("Türkçe late interaction")

    assert first == second
    assert 0 < len(first) <= encoder.max_tokens
    assert all(len(vector) == encoder.dimension for vector in first)


def test_late_interaction_reranks_hybrid_candidates_and_keeps_provenance() -> None:
    store = QdrantLateInteractionVectorStore(":memory:", "late_test")
    store.ensure_collection(3)
    payload = {
        "document_id": "doc_late",
        "chunk_id": "chunk_late",
        "text": "late interaction target",
        "source_uri": "file:///late.md",
        "title": "Late",
        "location": {"start_line": 1},
        "embedding_manifest_id": FakeProvider.manifest.manifest_id,
        "owner_id": "me",
        "document_status": "active",
    }
    store.upsert(
        [
            models.PointStruct(
                id=str(uuid4()),
                vector=store.prepare_vector([1.0, 0.0, 0.0], payload["text"]),
                payload=payload,
            )
        ]
    )

    results = RetrievalService(FakeProvider(), store).search("late target", limit=1)

    assert len(results) == 1
    assert results[0].retrieval_stage == "late_interaction"
    assert results[0].source_uri == "file:///late.md"
