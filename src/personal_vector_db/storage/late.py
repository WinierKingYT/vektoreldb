"""Opt-in dense+sparse candidate retrieval with late-interaction reranking."""

from collections.abc import Sequence

from qdrant_client.http import models

from personal_vector_db.embeddings import LateInteractionEncoder
from personal_vector_db.retrieval import RetrievalFilter

from .hybrid import QdrantHybridVectorStore


class QdrantLateInteractionVectorStore(QdrantHybridVectorStore):
    """Qdrant collection with a non-HNSW multi-vector rerank representation."""

    def __init__(self, *args, late_encoder: LateInteractionEncoder | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.late_encoder = late_encoder or LateInteractionEncoder()

    def ensure_collection(self, dimension: int) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=dimension, distance=models.Distance.COSINE
                    ),
                    "late": models.VectorParams(
                        size=self.late_encoder.dimension,
                        distance=models.Distance.COSINE,
                        multivector_config=models.MultiVectorConfig(
                            comparator=models.MultiVectorComparator.MAX_SIM
                        ),
                        hnsw_config=models.HnswConfigDiff(m=0),
                    ),
                },
                sparse_vectors_config={"sparse": models.SparseVectorParams()},
            )
        else:
            vectors = self.client.get_collection(self.collection_name).config.params.vectors
            if not isinstance(vectors, dict) or not {"dense", "late"}.issubset(vectors):
                raise ValueError("late collection must contain dense and late named vectors")
            dense = vectors["dense"]
            late = vectors["late"]
            if dense.size != dimension or dense.distance != models.Distance.COSINE:
                raise ValueError("late collection dense contract does not match provider")
            if late.size != self.late_encoder.dimension or late.multivector_config is None:
                raise ValueError("late collection multi-vector contract does not match encoder")
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
        vector = super().prepare_vector(dense, text)
        vector["late"] = self.late_encoder.encode(text)
        return vector

    def late_search(
        self,
        dense_vector: Sequence[float],
        *,
        query: str,
        limit: int = 10,
        filters: RetrievalFilter | None = None,
        exact: bool = False,
    ) -> list[models.ScoredPoint]:
        candidates = super().hybrid_search(
            dense_vector,
            query=query,
            limit=min(100, max(limit * 3, 10)),
            filters=filters,
            exact=exact,
        )
        if not candidates:
            return []
        candidate_ids = [candidate.id for candidate in candidates]
        query_filter = self._filter(filters)
        query_filter.must.append(models.HasIdCondition(has_id=candidate_ids))
        return self.client.query_points(
            collection_name=self.collection_name,
            query=self.late_encoder.encode(query),
            using="late",
            query_filter=query_filter,
            search_params=models.SearchParams(exact=True),
            limit=limit,
            with_payload=True,
        ).points
