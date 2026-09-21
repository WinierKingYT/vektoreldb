"""Production composition root for the retrieval API."""

from personal_vector_db.api import create_app
from personal_vector_db.config import Settings, validate_runtime_settings
from personal_vector_db.embeddings import create_embedding_provider
from personal_vector_db.ingest import IngestService
from personal_vector_db.planner import SelectivityQueryPlanner
from personal_vector_db.reranking import LexicalOverlapReranker
from personal_vector_db.retrieval import RetrievalService
from personal_vector_db.storage import (
    QdrantHybridVectorStore,
    QdrantLateInteractionVectorStore,
    QdrantQuantizedVectorStore,
    QdrantVectorStore,
)


def create_production_app():
    settings = Settings()
    validate_runtime_settings(settings)
    provider = create_embedding_provider(settings)
    store_type = {
        "dense": QdrantVectorStore,
        "hybrid": QdrantHybridVectorStore,
        "late": QdrantLateInteractionVectorStore,
        "quantized": QdrantQuantizedVectorStore,
    }[settings.retrieval_mode]
    collection_name = {
        "dense": settings.collection_name,
        "hybrid": settings.hybrid_collection_name,
        "late": settings.late_collection_name,
        "quantized": settings.quantized_collection_name,
    }[settings.retrieval_mode]
    store = store_type(settings.qdrant_url, collection_name, hnsw_ef=settings.hnsw_ef)
    store.ensure_collection(provider.manifest.dimension)
    store.ensure_manifest(provider.manifest.manifest_id)
    ingest = IngestService(
        provider,
        store,
        source_root=settings.data_dir / "sources",
        max_source_bytes=settings.source_max_bytes,
        max_directory_files=settings.source_max_files,
        max_directory_bytes=settings.source_max_total_bytes,
    )
    planner = SelectivityQueryPlanner() if settings.query_planner_mode == "selectivity" else None
    reranker = LexicalOverlapReranker() if settings.reranker_mode == "lexical" else None
    return create_app(
        RetrievalService(
            provider,
            store,
            reranker=reranker,
            planner=planner,
            default_min_score=settings.retrieval_min_score,
        ),
        ingest,
    )


app = create_production_app()
