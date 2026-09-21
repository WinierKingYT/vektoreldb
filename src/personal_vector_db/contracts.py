"""Stable boundaries between ingest, embedding, storage and retrieval."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmbeddingManifest:
    provider: str
    model: str
    revision: str
    dimension: int
    metric: str
    normalized: bool

    @property
    def manifest_id(self) -> str:
        return (
            f"{self.provider}:{self.model}@{self.revision}:"
            f"{self.dimension}:{self.metric}:norm={self.normalized}"
        )


class EmbeddingProvider(Protocol):
    manifest: EmbeddingManifest

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class VectorStore(Protocol):
    def healthcheck(self) -> bool: ...

    def upsert(self, points: Sequence[object]) -> None: ...

    def search(
        self,
        vector: Sequence[float],
        limit: int = 10,
        filters: object | None = None,
        exact: bool = False,
    ) -> list[object]: ...

    def delete_document(self, document_id: str) -> None: ...

    def replace_document(self, document_id: str, points: Sequence[object]) -> None: ...
