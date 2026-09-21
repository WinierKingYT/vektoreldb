"""Typed application configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(default="dev", alias="VDB_ENV")
    data_dir: Path = Field(default=Path("data"), alias="VDB_DATA_DIR")
    qdrant_url: str = Field(default="path:qdrant_storage", alias="VDB_QDRANT_URL")
    collection_name: str = Field(default="personal_documents_v1", alias="VDB_COLLECTION_NAME")
    hybrid_collection_name: str = Field(
        default="personal_documents_hybrid_v1", alias="VDB_HYBRID_COLLECTION_NAME"
    )
    late_collection_name: str = Field(
        default="personal_documents_late_v1", alias="VDB_LATE_COLLECTION_NAME"
    )
    quantized_collection_name: str = Field(
        default="personal_documents_quantized_v1", alias="VDB_QUANTIZED_COLLECTION_NAME"
    )
    retrieval_mode: str = Field(default="dense", alias="VDB_RETRIEVAL_MODE")
    reranker_mode: str = Field(default="off", alias="VDB_RERANKER_MODE")
    query_planner_mode: str = Field(default="off", alias="VDB_QUERY_PLANNER_MODE")
    embedding_provider: str = Field(default="local", alias="VDB_EMBEDDING_PROVIDER")
    embedding_model: str = Field(
        default="intfloat/multilingual-e5-base", alias="VDB_EMBEDDING_MODEL"
    )
    embedding_revision: str = Field(
        default="d128750597153bb5987e10b1c3493a34e5a4502a",
        alias="VDB_EMBEDDING_REVISION",
    )
    embedding_offline: bool = Field(default=False, alias="VDB_EMBEDDING_OFFLINE")
    embedding_base_url: str = Field(
        default="https://api.openai.com/v1", alias="VDB_EMBEDDING_BASE_URL"
    )
    embedding_timeout_seconds: float = Field(
        default=30.0, alias="VDB_EMBEDDING_TIMEOUT_SECONDS", gt=0
    )
    embedding_max_retries: int = Field(default=2, alias="VDB_EMBEDDING_MAX_RETRIES", ge=0, le=5)
    embedding_batch_size: int = Field(
        default=32, alias="VDB_EMBEDDING_BATCH_SIZE", ge=1, le=256
    )
    embedding_cache_size: int = Field(
        default=256, alias="VDB_EMBEDDING_CACHE_SIZE", ge=0, le=4096
    )
    vector_dimension: int = Field(default=768, alias="VDB_VECTOR_DIMENSION", gt=0)
    distance_metric: str = Field(default="cosine", alias="VDB_DISTANCE_METRIC")
    hnsw_ef: int | None = Field(default=None, alias="VDB_HNSW_EF", gt=0)
    retrieval_min_score: float | None = Field(
        default=None, alias="VDB_RETRIEVAL_MIN_SCORE", ge=-1, le=1
    )
    source_max_bytes: int = Field(default=10_000_000, alias="VDB_SOURCE_MAX_BYTES", gt=0)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


def validate_runtime_settings(settings: Settings) -> None:
    """Fail closed when configured values are outside the implemented V1 contract."""

    if settings.embedding_provider not in {"local", "openai"}:
        raise ValueError(
            f"unsupported embedding provider {settings.embedding_provider!r}; "
            "choose 'local' or opt-in 'openai'"
        )
    if settings.retrieval_mode not in {"dense", "hybrid", "late", "quantized"}:
        raise ValueError(
            "unsupported retrieval mode; choose 'dense', 'hybrid', 'late' or 'quantized'"
        )
    if settings.reranker_mode not in {"off", "lexical"}:
        raise ValueError("unsupported reranker mode; choose 'off' or 'lexical'")
    if settings.query_planner_mode not in {"off", "selectivity"}:
        raise ValueError("unsupported query planner mode; choose 'off' or 'selectivity'")
    if settings.distance_metric != "cosine":
        raise ValueError(
            f"unsupported distance metric {settings.distance_metric!r}; "
            "only 'cosine' is implemented in V1"
        )
