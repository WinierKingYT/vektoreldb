import json
from types import SimpleNamespace

import pytest
from qdrant_client.http import models

from personal_vector_db.contracts import EmbeddingManifest
from personal_vector_db.planner import SelectivityQueryPlanner
from personal_vector_db.reranking import LexicalOverlapReranker
from personal_vector_db.retrieval import ExactVectorStore, RetrievalFilter, RetrievalService


class FakeProvider:
    manifest = EmbeddingManifest("test", "model", "r1", 3, "cosine", True)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0] if "bir" in text else [0.0, 1.0, 0.0]


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
        },
    )


def test_exact_baseline_returns_rag_safe_provenance() -> None:
    store = ExactVectorStore()
    store.upsert([point("1", [1.0, 0.0, 0.0], "doc_a", "bir içerik")])

    results = RetrievalService(FakeProvider(), store).search("bir soru")

    assert len(results) == 1
    assert results[0].document_id == "doc_a"
    assert results[0].source_uri == "file:///notes.md"
    assert results[0].retrieval_stage == "dense"


def test_search_rejects_invalid_limit() -> None:
    try:
        RetrievalService(FakeProvider(), ExactVectorStore()).search("soru", limit=0)
    except ValueError as error:
        assert "between" in str(error)
    else:
        raise AssertionError("invalid limit must be rejected")


def test_search_rejects_oversized_query() -> None:
    with pytest.raises(ValueError, match="characters"):
        RetrievalService(FakeProvider(), ExactVectorStore()).search("x" * 4_001)


def test_search_applies_min_score_before_top_k_truncation() -> None:
    service = RetrievalService(FakeProvider(), ExactVectorStore())
    service.store.upsert(
        [
            point("one", [0.9, 0.435889894, 0.0], "doc_below", "eşik altı"),
            point("two", [0.0, 1.0, 0.0], "doc_above", "eşik üstü"),
        ]
    )

    results = service.search("soru", limit=1, min_score=0.95)

    assert [result.document_id for result in results] == ["doc_above"]


@pytest.mark.parametrize("min_score", [-1.1, 1.1, float("nan"), float("inf")])
def test_search_rejects_invalid_min_score(min_score: float) -> None:
    with pytest.raises(ValueError, match="min_score"):
        RetrievalService(FakeProvider(), ExactVectorStore()).search(
            "soru", min_score=min_score
        )


def test_exact_replacement_preserves_other_owner_with_same_document_id() -> None:
    store = ExactVectorStore()
    store.upsert(
        [
            point("owned-old", [1.0, 0.0, 0.0], "shared", "owned old"),
            models.PointStruct(
                id="other-owner",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "document_id": "shared",
                    "chunk_id": "other",
                    "content_hash": "sha256:" + "z" * 64,
                    "owner_id": "someone-else",
                    "document_status": "active",
                },
            ),
        ]
    )
    replacement = point("owned-new", [0.0, 1.0, 0.0], "shared", "owned new")
    replacement.payload["content_hash"] = "sha256:" + "y" * 64

    store.replace_document("shared", [replacement])

    assert any(point.id == "other-owner" for _, point in store._points)


def test_exact_store_rejects_invalid_limit() -> None:
    store = ExactVectorStore()
    store.upsert([point("one", [1.0, 0.0, 0.0], "doc", "içerik")])

    with pytest.raises(ValueError, match="between"):
        store.search([1.0, 0.0, 0.0], limit=0)


def test_exact_baseline_applies_owner_and_status_filters() -> None:
    store = ExactVectorStore()
    store.upsert(
        [
            point("1", [1.0, 0.0, 0.0], "doc_owner", "başka kullanıcı"),
            point("2", [1.0, 0.0, 0.0], "doc_status", "pasif"),
        ]
    )
    store._points[0][1].payload["owner_id"] = "someone-else"
    store._points[1][1].payload["document_status"] = "deleted"

    assert store.search([1.0, 0.0, 0.0]) == []


def test_metadata_filters_are_applied_without_bypassing_owner_or_status() -> None:
    store = ExactVectorStore()
    first = point("first", [1.0, 0.0, 0.0], "doc_first", "ilk")
    second = point("second", [1.0, 0.0, 0.0], "doc_second", "ikinci")
    second.payload["source_type"] = "markdown"
    first.payload["source_type"] = "text"
    store.upsert([first, second])

    results = store.search(
        [1.0, 0.0, 0.0],
        filters=RetrievalFilter(source_types=("markdown",)),
    )

    assert [item.payload["document_id"] for item in results] == ["doc_second"]


def test_retrieval_audit_event_contains_metrics_without_query_text(caplog) -> None:
    service = RetrievalService(FakeProvider(), ExactVectorStore())
    service.store.upsert([point("one", [1.0, 0.0, 0.0], "doc", "gizli metin")])

    with caplog.at_level("INFO", logger="personal_vector_db.audit"):
        service.search("benzersiz gizli sorgu", filters=RetrievalFilter(titles=("Notes",)))

    record = caplog.records[-1].message
    assert "candidate_count" in record
    assert "latency_ms" in record
    assert "filter_fields" in record
    assert "benzersiz gizli sorgu" not in record


def test_retrieval_audit_distinguishes_threshold_abstention(caplog) -> None:
    service = RetrievalService(FakeProvider(), ExactVectorStore())
    service.store.upsert([point("one", [1.0, 0.0, 0.0], "doc", "içerik")])

    with caplog.at_level("INFO", logger="personal_vector_db.audit"):
        assert service.search("soru", min_score=0.9) == []

    record = json.loads(caplog.records[-1].message)
    assert record["abstention"] is True
    assert record["abstention_reason"] == "below_min_score"
    assert record["threshold_rejected_count"] == 1


def test_opt_in_reranker_rescores_only_candidates_and_preserves_provenance() -> None:
    store = ExactVectorStore()
    first = point("first", [1.0, 0.0, 0.0], "doc_first", "genel içerik")
    second = point("second", [1.0, 0.0, 0.0], "doc_second", "bir hedef içeriği")
    store.upsert([first, second])

    results = RetrievalService(
        FakeProvider(), store, LexicalOverlapReranker()
    ).search("bir hedef", limit=1, rerank=True)

    assert [result.document_id for result in results] == ["doc_second"]
    assert results[0].retrieval_stage == "dense+rerank"
    assert results[0].source_uri == "file:///notes.md"


def test_min_score_filters_retrieval_scores_before_reranking() -> None:
    class MisalignedScaleReranker:
        name = "misaligned-scale"

        def __init__(self) -> None:
            self.seen: list[str] = []

        def score(self, query: str, texts: list[str]) -> list[float]:
            self.seen.extend(texts)
            return [0.1 if text == "base-score-passes" else 0.99 for text in texts]

    store = ExactVectorStore()
    store.upsert(
        [
            point("below", [0.8, 0.6, 0.0], "doc_below", "base-score-fails"),
            point("above", [0.6, 0.8, 0.0], "doc_above", "base-score-passes"),
        ]
    )
    reranker = MisalignedScaleReranker()

    results = RetrievalService(FakeProvider(), store, reranker).search(
        "target query", min_score=0.75, rerank=True
    )

    assert [result.document_id for result in results] == ["doc_above"]
    assert reranker.seen == ["base-score-passes"]
    assert results[0].score == 0.1
    assert results.threshold_rejected_count == 1


@pytest.mark.parametrize("min_score", [True, "0.5"])
def test_search_rejects_non_numeric_or_boolean_min_score(min_score: object) -> None:
    with pytest.raises(ValueError, match="min_score"):
        RetrievalService(FakeProvider(), ExactVectorStore()).search(
            "soru", min_score=min_score  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("mode", ["hybrid", "late"])
def test_min_score_fails_closed_for_uncalibrated_retrieval_modes(mode: str) -> None:
    class AlternateScoreStore(ExactVectorStore):
        def hybrid_search(self, *args, **kwargs):
            raise AssertionError("unsupported threshold must fail before retrieval")

        def late_search(self, *args, **kwargs):
            raise AssertionError("unsupported threshold must fail before retrieval")

    store = AlternateScoreStore()
    if mode == "hybrid":
        store.late_search = None  # type: ignore[method-assign]
    else:
        store.hybrid_search = None  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="dense cosine retrieval only"):
        RetrievalService(FakeProvider(), store).search("query", min_score=0.5)


def test_reranker_failure_falls_back_to_original_candidates() -> None:
    class BrokenReranker:
        name = "broken"

        def score(self, query, texts):
            raise RuntimeError("model unavailable")

    store = ExactVectorStore()
    store.upsert([point("one", [1.0, 0.0, 0.0], "doc", "içerik")])

    results = RetrievalService(FakeProvider(), store, BrokenReranker()).search(
        "bir soru", rerank=True
    )

    assert len(results) == 1
    assert results[0].retrieval_stage == "dense"


def test_selectivity_planner_is_used_for_filtered_exact_baseline() -> None:
    store = ExactVectorStore()
    first = point("first", [1.0, 0.0, 0.0], "doc_first", "ilk")
    second = point("second", [1.0, 0.0, 0.0], "doc_second", "ikinci")
    second.payload["title"] = "Target"
    store.upsert([first, second])

    results = RetrievalService(
        FakeProvider(), store, planner=SelectivityQueryPlanner()
    ).search("bir soru", filters=RetrievalFilter(titles=("Target",)))

    assert [result.document_id for result in results] == ["doc_second"]


def test_exact_baseline_upsert_is_idempotent_by_point_id() -> None:
    store = ExactVectorStore()
    original = point("same", [1.0, 0.0, 0.0], "doc", "eski")
    replacement = point("same", [0.0, 1.0, 0.0], "doc", "yeni")

    store.upsert([original])
    store.upsert([replacement])

    assert len(store._points) == 1
    assert store.search([0.0, 1.0, 0.0])[0].payload["text"] == "yeni"


def test_exact_baseline_rejects_dimension_mismatch() -> None:
    store = ExactVectorStore()
    store.upsert([point("one", [1.0, 0.0, 0.0], "doc", "içerik")])

    try:
        store.search([1.0, 0.0])
    except ValueError as error:
        assert "dimension" in str(error)
    else:
        raise AssertionError("dimension mismatch must be rejected")


def test_exact_baseline_invalid_first_upsert_does_not_poison_dimension() -> None:
    store = ExactVectorStore()
    try:
        store.upsert([point("invalid", [0.0, 0.0], "doc", "içerik")])
    except ValueError:
        pass
    else:
        raise AssertionError("zero vector must be rejected")

    store.upsert([point("valid", [1.0, 0.0, 0.0], "doc", "içerik")])
    assert store.search([1.0, 0.0, 0.0])[0].payload["chunk_id"] == "doc_chunk_1"


def test_exact_baseline_rejects_non_numeric_vector_values() -> None:
    store = ExactVectorStore()
    with pytest.raises(ValueError, match="numeric"):
        store.upsert(
            [
                SimpleNamespace(
                    id="bad",
                    vector=["x", 0.0, 1.0],
                    payload={"document_id": "doc", "chunk_id": "chunk"},
                )
            ]
        )


@pytest.mark.parametrize(
    ("query", "message"),
    [(["x", 0.0, 1.0], "numeric"), ([float("nan"), 0.0, 1.0], "finite")],
)
def test_exact_baseline_rejects_invalid_query_vectors(
    query: list[object], message: str
) -> None:
    store = ExactVectorStore()
    store.upsert([point("one", [1.0, 0.0, 0.0], "doc", "içerik")])

    with pytest.raises(ValueError, match=message):
        store.search(query)
