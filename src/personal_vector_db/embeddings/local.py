"""Local Sentence Transformers embedding provider."""

from collections.abc import Sequence
from math import isfinite
from typing import Any

from personal_vector_db.contracts import EmbeddingManifest


class LocalEmbeddingProvider:
    """Encode query/document text with a pinned local Sentence Transformer.

    The model is loaded lazily. Tests and alternative runtimes may inject a
    compatible model object, avoiding a network download during construction.
    """

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-base",
        *,
        revision: str = "d128750597153bb5987e10b1c3493a34e5a4502a",
        dimension: int = 768,
        model: Any | None = None,
        offline: bool = False,
    ) -> None:
        self.manifest = EmbeddingManifest(
            provider="local-sentence-transformers",
            model=model_name,
            revision=revision,
            dimension=dimension,
            metric="cosine",
            normalized=True,
        )
        self._model = model
        self._offline = offline

    def _get_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            try:
                loader_kwargs = {"revision": self.manifest.revision}
                if self._offline:
                    loader_kwargs["local_files_only"] = True
                self._model = SentenceTransformer(self.manifest.model, **loader_kwargs)
            except (OSError, RuntimeError) as error:
                raise self._unavailable_error(error) from error
        return self._model

    def _unavailable_error(self, error: Exception) -> RuntimeError:
        return RuntimeError(
            f"embedding model {self.manifest.model!r} is unavailable; "
            "download it once or configure a complete local Hugging Face cache"
        )

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ValueError("embedding input cannot contain empty text")
        try:
            vectors = self._get_model().encode(
                list(texts),
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except (OSError, RuntimeError) as error:
            if "embedding model" in str(error) and "unavailable" in str(error):
                raise
            raise self._unavailable_error(error) from error
        result = [
            vector.tolist() if hasattr(vector, "tolist") else list(vector) for vector in vectors
        ]
        if any(len(vector) != self.manifest.dimension for vector in result):
            raise ValueError("embedding dimension does not match manifest")
        if any(not all(isfinite(value) for value in vector) for vector in result):
            raise ValueError("embedding contains non-finite values")
        if any(sum(value * value for value in vector) == 0 for vector in result):
            raise ValueError("embedding vector cannot have zero norm")
        return result

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode([f"passage: {text}" for text in texts])

    def embed_query(self, text: str) -> list[float]:
        vectors = self._encode([f"query: {text}"])
        return vectors[0]
