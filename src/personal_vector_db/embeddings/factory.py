"""Embedding provider composition with explicit opt-in boundaries."""

import os
from urllib.parse import urlsplit

from personal_vector_db.audit import emit_audit_event
from personal_vector_db.config import Settings
from personal_vector_db.contracts import EmbeddingProvider

from .local import LocalEmbeddingProvider
from .openai import OpenAIEmbeddingProvider


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "local":
        return LocalEmbeddingProvider(
            model_name=settings.embedding_model,
            revision=settings.embedding_revision,
            dimension=settings.vector_dimension,
            offline=settings.embedding_offline,
        )
    if settings.embedding_provider == "openai":
        provider = OpenAIEmbeddingProvider(
            settings.embedding_model,
            dimension=settings.vector_dimension,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=settings.embedding_base_url,
            timeout_seconds=settings.embedding_timeout_seconds,
            max_retries=settings.embedding_max_retries,
            batch_size=settings.embedding_batch_size,
            cache_size=settings.embedding_cache_size,
        )
        endpoint = urlsplit(settings.embedding_base_url)
        emit_audit_event(
            "external_embedding_provider_selected",
            provider="openai-compatible",
            model=settings.embedding_model,
            endpoint_scheme=endpoint.scheme,
            endpoint_host=endpoint.hostname or "",
            dimension=settings.vector_dimension,
        )
        return provider
    raise ValueError(f"unsupported embedding provider {settings.embedding_provider!r}")
