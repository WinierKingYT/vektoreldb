"""Opt-in scalar-quantized Qdrant adapter for the V1.6 experiment."""

from collections.abc import Sequence

from qdrant_client.http import models

from personal_vector_db.retrieval import RetrievalFilter

from .qdrant import QdrantVectorStore


class QdrantQuantizedVectorStore(QdrantVectorStore):
    """Dense collection with INT8 quantization and original-vector rescoring."""

    def __init__(
        self,
        *args,
        oversampling: float = 2.0,
        rescore: bool = True,
        **kwargs,
    ):
        if oversampling < 1:
            raise ValueError("quantization oversampling must be at least 1")
        super().__init__(*args, **kwargs)
        self.oversampling = oversampling
        self.rescore = rescore

    def ensure_collection(self, dimension: int) -> None:
        quantization = models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(type=models.ScalarType.INT8)
        )
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=dimension, distance=models.Distance.COSINE
                ),
                quantization_config=quantization,
            )
        else:
            collection = self.client.get_collection(self.collection_name)
            vectors = collection.config.params.vectors
            if not isinstance(vectors, models.VectorParams):
                raise ValueError("quantized collection must use the dense V1 vector")
            if vectors.size != dimension or vectors.distance != models.Distance.COSINE:
                raise ValueError("quantized dense vector contract does not match provider")
            if collection.config.quantization_config is None:
                raise ValueError("collection is not configured for quantization")
        if self._local_mode:
            if self.client.get_collection(self.collection_name).config.quantization_config is None:
                raise RuntimeError("Qdrant quantization requires a server runtime")
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

    def search(
        self,
        vector: Sequence[float],
        limit: int = 10,
        filters: RetrievalFilter | None = None,
        exact: bool = False,
    ) -> list[models.ScoredPoint]:
        quantization = models.QuantizationSearchParams(
            rescore=self.rescore,
            oversampling=self.oversampling,
        )
        return super().search(
            vector, limit=limit, filters=filters, exact=exact, quantization=quantization
        )
