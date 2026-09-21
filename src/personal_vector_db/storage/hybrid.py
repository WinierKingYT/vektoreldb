"""Opt-in Qdrant dense+sparse RRF adapter for the V1.2 experiment."""

from collections.abc import Sequence

from qdrant_client.http import models

from personal_vector_db.embeddings import SparseLexicalEncoder
from personal_vector_db.retrieval import RetrievalFilter

from .qdrant import QdrantVectorStore


class QdrantHybridVectorStore(QdrantVectorStore):
    """Named dense/sparse collection with server-side RRF fusion."""

    def __init__(self, *args, sparse_encoder: SparseLexicalEncoder | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sparse_encoder = sparse_encoder or SparseLexicalEncoder()

    def ensure_collection(self, dimension: int) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=dimension, distance=models.Distance.COSINE
                    )
                },
                sparse_vectors_config={"sparse": models.SparseVectorParams()},
            )
        else:
            vectors = self.client.get_collection(self.collection_name).config.params.vectors
            if not isinstance(vectors, dict) or "dense" not in vectors:
                raise ValueError("hybrid collection must contain a named dense vector")
            dense = vectors["dense"]
            if dense.size != dimension or dense.distance != models.Distance.COSINE:
                raise ValueError("hybrid dense vector contract does not match provider")
        if self._local_mode:
            return
        for field in (
            "document_id",
            "owner_id",
            "document_status",
            "source_uri",
            "source_type",
            "title",
        ):
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                    wait=True,
                )
            except Exception as error:
                if "already exists" not in str(error).lower():
                    raise

    def prepare_vector(self, dense: Sequence[float], text: str) -> dict[str, object]:
        return {"dense": list(dense), "sparse": self.sparse_encoder.encode(text)}

    @staticmethod
    def _filter(filters: RetrievalFilter | None) -> models.Filter:
        conditions = [
            models.FieldCondition(key="owner_id", match=models.MatchValue(value="me")),
            models.FieldCondition(
                key="document_status", match=models.MatchValue(value="active")
            ),
        ]
        if filters:
            for field, values in filters.as_mapping().items():
                conditions.append(
                    models.FieldCondition(
                        key=field, match=models.MatchAny(any=list(values))
                    )
                )
        return models.Filter(must=conditions)

    def hybrid_search(
        self,
        dense_vector: Sequence[float],
        *,
        query: str,
        limit: int = 10,
        filters: RetrievalFilter | None = None,
        exact: bool = False,
    ) -> list[models.ScoredPoint]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        query_filter = self._filter(filters)
        candidate_limit = min(100, max(limit * 2, 20))
        return self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=list(dense_vector),
                    using="dense",
                    filter=query_filter,
                    params=models.SearchParams(exact=exact),
                    limit=candidate_limit,
                ),
                models.Prefetch(
                    query=self.sparse_encoder.encode(query),
                    using="sparse",
                    filter=query_filter,
                    params=models.SearchParams(exact=exact),
                    limit=candidate_limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        ).points

    def filter_selectivity(self, filters: RetrievalFilter) -> float:
        return super().filter_selectivity(filters)
