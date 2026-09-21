"""Provider-agnostic retrieval response with RAG-safe provenance."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from time import perf_counter

from qdrant_client.http import models

from personal_vector_db.audit import emit_audit_event, text_fingerprint
from personal_vector_db.contracts import EmbeddingProvider, VectorStore
from personal_vector_db.planner import SelectivityQueryPlanner
from personal_vector_db.reranking import Reranker

MAX_QUERY_CHARS = 4_000


@dataclass(frozen=True)
class RetrievalResult:
    document_id: str
    chunk_id: str
    text: str
    score: float
    source_uri: str
    title: str
    location: dict[str, object]
    embedding_manifest_id: str
    retrieval_stage: str = "dense"
    parser_version: str = "unknown"
    document_status: str = "active"
    security_flags: tuple[str, ...] = ()
    heading_path: tuple[str, ...] = ()


class RetrievalResults(list[RetrievalResult]):
    """List-compatible results with privacy-safe abstention diagnostics."""

    def __init__(
        self,
        results: Sequence[RetrievalResult],
        *,
        candidate_count: int,
        threshold_rejected_count: int,
        abstention_reason: str,
    ) -> None:
        super().__init__(results)
        self.candidate_count = candidate_count
        self.threshold_rejected_count = threshold_rejected_count
        self.abstention_reason = abstention_reason


@dataclass(frozen=True)
class RetrievalFilter:
    """User-selectable metadata filters; ownership/status remain server-owned."""

    document_ids: tuple[str, ...] = ()
    source_uris: tuple[str, ...] = ()
    source_types: tuple[str, ...] = ()
    titles: tuple[str, ...] = ()

    def as_mapping(self) -> Mapping[str, tuple[str, ...]]:
        return {
            key: values
            for key, values in (
                ("document_id", self.document_ids),
                ("source_uri", self.source_uris),
                ("source_type", self.source_types),
                ("title", self.titles),
            )
            if values
        }


class RetrievalService:
    def __init__(
        self,
        provider: EmbeddingProvider,
        store: VectorStore,
        reranker: Reranker | None = None,
        planner: SelectivityQueryPlanner | None = None,
        default_min_score: float | None = None,
    ) -> None:
        if default_min_score is not None and not isfinite(default_min_score):
            raise ValueError("default_min_score must be finite")
        if default_min_score is not None and not -1.0 <= default_min_score <= 1.0:
            raise ValueError("default_min_score must be between -1 and 1")
        self.provider = provider
        self.store = store
        self.reranker = reranker
        self.planner = planner
        self.default_min_score = default_min_score

    def search(
        self,
        query: str,
        *,
        limit: int = 8,
        min_score: float | None = None,
        filters: RetrievalFilter | None = None,
        rerank: bool = False,
    ) -> RetrievalResults:
        started = perf_counter()
        if not query.strip():
            raise ValueError("query cannot be empty")
        if len(query) > MAX_QUERY_CHARS:
            raise ValueError(f"query cannot exceed {MAX_QUERY_CHARS} characters")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        effective_min_score = self.default_min_score if min_score is None else min_score
        if effective_min_score is not None and (
            isinstance(effective_min_score, bool)
            or not isinstance(effective_min_score, (int, float))
            or not isfinite(effective_min_score)
            or not -1.0 <= effective_min_score <= 1.0
        ):
            raise ValueError("min_score must be between -1 and 1")
        # Apply the score threshold before truncating to top-k. Otherwise an
        # under-threshold result occupying the first slot can hide a valid
        # result immediately after it. V1 backends cap a single search at 100.
        candidate_limit = 100 if effective_min_score is not None else limit
        if rerank:
            if self.reranker is None:
                raise ValueError("reranking is not configured")
            candidate_limit = min(100, max(limit * 3, 10))
        late_search = getattr(self.store, "late_search", None)
        hybrid_search = getattr(self.store, "hybrid_search", None)
        if effective_min_score is not None and (
            callable(late_search) or callable(hybrid_search)
        ):
            raise ValueError(
                "min_score currently supports dense cosine retrieval only; "
                "hybrid and late-interaction thresholds require separate calibration"
            )
        selectivity = None
        if self.planner is not None and filters and filters.as_mapping():
            estimate = getattr(self.store, "filter_selectivity", None)
            if callable(estimate):
                selectivity = estimate(filters)
        plan = (
            self.planner.plan(
                selectivity,
                limit=candidate_limit,
                has_user_filter=bool(filters and filters.as_mapping()),
            )
            if self.planner is not None
            else None
        )
        if plan is not None:
            candidate_limit = plan.candidate_limit
        embedding_started = perf_counter()
        dense_vector = self.provider.embed_query(query)
        embedding_latency_ms = round((perf_counter() - embedding_started) * 1000, 3)
        if callable(late_search):
            points = late_search(
                dense_vector,
                query=query,
                limit=candidate_limit,
                filters=filters,
                exact=plan.exact if plan else False,
            )
            retrieval_stage = "late_interaction"
        elif callable(hybrid_search):
            points = hybrid_search(
                dense_vector,
                query=query,
                limit=candidate_limit,
                filters=filters,
                exact=plan.exact if plan else False,
            )
            retrieval_stage = "hybrid"
        else:
            points = self.store.search(
                dense_vector,
                limit=candidate_limit,
                filters=filters,
                exact=plan.exact if plan else False,
            )
            retrieval_stage = "dense"
        candidate_count = len(points)
        results = [self._result(point, retrieval_stage=retrieval_stage) for point in points]
        threshold_rejected_count = 0
        if effective_min_score is not None:
            # The threshold belongs to this retrieval mode's score scale.
            # Reranker scores may use another scale (e.g. cross-encoder logits),
            # so they only reorder candidates and never decide admission.
            threshold_rejected_count = sum(
                result.score < effective_min_score for result in results
            )
            results = [result for result in results if result.score >= effective_min_score]
        rerank_fallback = False
        if rerank and results:
            try:
                scores = self.reranker.score(query, [result.text for result in results])
                if len(scores) != len(results) or not all(isfinite(score) for score in scores):
                    raise ValueError("reranker returned invalid scores")
                results = [
                    RetrievalResult(
                        **{
                            **result.__dict__,
                            "score": score,
                            "retrieval_stage": f"{result.retrieval_stage}+rerank",
                        }
                    )
                    for result, score in zip(results, scores)
                ]
                results.sort(key=lambda result: result.score, reverse=True)
            except Exception:
                rerank_fallback = True
        results = results[:limit]
        if not results:
            abstention_reason = (
                "below_min_score"
                if effective_min_score is not None and threshold_rejected_count
                else "no_candidates"
            )
        else:
            abstention_reason = "none"
        emit_audit_event(
            "retrieval_completed",
            query_sha256=text_fingerprint(query),
            result_count=len(results),
            candidate_count=candidate_count,
            filtered_count=max(candidate_count - len(results), 0),
            abstention=not results,
            abstention_reason=abstention_reason,
            threshold_rejected_count=threshold_rejected_count,
            limit=limit,
            filter_fields=sorted(filters.as_mapping()) if filters else [],
            rerank_requested=rerank,
            reranker=getattr(self.reranker, "name", None) if rerank else None,
            rerank_fallback=rerank_fallback,
            planner_mode=plan.mode if plan else None,
            filter_selectivity=selectivity,
            embedding_manifest_id=self.provider.manifest.manifest_id,
            min_score=effective_min_score,
            embedding_latency_ms=embedding_latency_ms,
            query_char_count=len(query),
            latency_ms=round((perf_counter() - started) * 1000, 3),
        )
        return RetrievalResults(
            results,
            candidate_count=candidate_count,
            threshold_rejected_count=threshold_rejected_count,
            abstention_reason=abstention_reason,
        )

    def _result(self, point: object, *, retrieval_stage: str = "dense") -> RetrievalResult:
        payload = point.payload
        return RetrievalResult(
            document_id=payload["document_id"],
            chunk_id=payload["chunk_id"],
            text=payload["text"],
            score=point.score,
            source_uri=payload["source_uri"],
            title=payload.get("title", ""),
            location=payload.get("location", {}),
            heading_path=tuple(payload.get("heading_path", ())),
            embedding_manifest_id=payload["embedding_manifest_id"],
            retrieval_stage=retrieval_stage,
            parser_version=payload.get("parser_version", "unknown"),
            document_status=payload.get("document_status", "active"),
            security_flags=tuple(payload.get("security_flags", ())),
        )


class ExactVectorStore:
    """Small exact cosine baseline used for quality comparisons and tests."""

    def __init__(self) -> None:
        self._points: list[tuple[list[float], object]] = []
        self._dimension: int | None = None

    def healthcheck(self) -> bool:
        return True

    def upsert(self, points: Sequence[object]) -> None:
        replacements = {}
        for point in points:
            vector = list(point.vector)
            if not vector:
                raise ValueError("embedding vector cannot be empty")
            if self._dimension is not None and len(vector) != self._dimension:
                raise ValueError(
                    f"embedding dimension {len(vector)} does not match {self._dimension}"
                )
            try:
                finite = all(isfinite(value) for value in vector)
                norm_squared = sum(value * value for value in vector)
            except (TypeError, ValueError):
                raise ValueError("embedding vector must contain numeric values") from None
            if not finite:
                raise ValueError("embedding vector must contain finite values")
            if norm_squared <= 0:
                raise ValueError("embedding vector must be non-zero")
            if self._dimension is None:
                self._dimension = len(vector)
            replacements[point.id] = (vector, point)
        self._points = [
            (vector, point) for vector, point in self._points if point.id not in replacements
        ]
        self._points.extend(replacements.values())

    def search(
        self,
        vector: Sequence[float],
        limit: int = 10,
        filters: RetrievalFilter | None = None,
        exact: bool = False,
    ) -> list[object]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        vector = list(vector)
        if self._dimension is not None and len(vector) != self._dimension:
            raise ValueError(
                f"query dimension {len(vector)} does not match {self._dimension}"
            )
        try:
            finite = all(isfinite(value) for value in vector)
            norm_squared = sum(value * value for value in vector)
        except (TypeError, ValueError):
            raise ValueError("query vector must contain numeric values") from None
        if not finite:
            raise ValueError("query vector must contain finite values")
        if norm_squared <= 0:
            raise ValueError("query vector must be non-zero")
        norm = norm_squared**0.5
        scored = []
        for stored_vector, point in self._points:
            payload = point.payload or {}
            if payload.get("owner_id", "me") != "me":
                continue
            if payload.get("document_status", "active") != "active":
                continue
            if filters and any(
                values and payload.get(field) not in values
                for field, values in filters.as_mapping().items()
            ):
                continue
            stored_norm = sum(value * value for value in stored_vector) ** 0.5
            score = sum(a * b for a, b in zip(vector, stored_vector)) / (norm * stored_norm)
            scored.append(
                models.ScoredPoint(
                    id=point.id,
                    version=0,
                    score=score,
                    payload=point.payload,
                    vector=None,
                )
            )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]

    def filter_selectivity(self, filters: RetrievalFilter) -> float:
        active = [
            point
            for _, point in self._points
            if (point.payload or {}).get("owner_id", "me") == "me"
            and (point.payload or {}).get("document_status", "active") == "active"
        ]
        if not active:
            return 0.0
        values = filters.as_mapping()
        matched = sum(
            all(point.payload.get(field) in allowed for field, allowed in values.items())
            for point in active
        )
        return matched / len(active)

    def delete_document(self, document_id: str) -> None:
        self._points = [
            (vector, point)
            for vector, point in self._points
            if point.payload.get("document_id") != document_id
            or point.payload.get("owner_id", "me") != "me"
        ]

    def replace_document(self, document_id: str, points: Sequence[object]) -> None:
        """Mirror Qdrant's replacement order for exact-baseline tests."""

        if not points:
            raise ValueError("replacement points cannot be empty")
        document_ids = {point.payload.get("document_id") for point in points}
        if document_ids != {document_id}:
            raise ValueError("replacement points must belong to document_id")
        owners = {point.payload.get("owner_id", "me") for point in points}
        if owners != {"me"}:
            raise ValueError("replacement points must belong to the V1 owner")
        content_hashes = {point.payload.get("content_hash") for point in points}
        if len(content_hashes) != 1 or None in content_hashes:
            raise ValueError("replacement points must share one content hash")
        content_hash = next(iter(content_hashes))
        self.upsert(points)
        self._points = [
            (vector, point)
            for vector, point in self._points
            if point.payload.get("document_id") != document_id
            or point.payload.get("owner_id", "me") != "me"
            or point.payload.get("content_hash") == content_hash
        ]
