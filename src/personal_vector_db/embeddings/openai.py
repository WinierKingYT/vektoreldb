"""Opt-in OpenAI-compatible embeddings provider.

The adapter is intentionally small and fail-closed: it never activates unless
the application configuration selects it and an API key is supplied by the
environment. No key or input text is written to logs.
"""

import hashlib
import json
import os
from collections import OrderedDict
from collections.abc import Sequence
from math import isfinite
from threading import RLock
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from personal_vector_db.contracts import EmbeddingManifest

_MAX_RESPONSE_BYTES = 64_000_000


class OpenAIEmbeddingProvider:
    """Call the OpenAI-compatible ``/embeddings`` endpoint for text vectors."""

    def __init__(
        self,
        model_name: str,
        *,
        dimension: int,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        batch_size: int = 32,
        cache_size: int = 256,
    ) -> None:
        if not model_name.strip():
            raise ValueError("embedding model cannot be empty")
        if dimension < 1:
            raise ValueError("embedding dimension must be positive")
        parsed_base_url = urlparse(base_url)
        hostname = (parsed_base_url.hostname or "").lower()
        local_http = parsed_base_url.scheme == "http" and hostname in {
            "localhost",
            "127.0.0.1",
            "::1",
        }
        if (
            (parsed_base_url.scheme != "https" and not local_http)
            or not parsed_base_url.netloc
            or parsed_base_url.username is not None
            or parsed_base_url.password is not None
            or parsed_base_url.query
            or parsed_base_url.fragment
        ):
            raise ValueError(
                "embedding base_url must use HTTPS; HTTP is allowed only for loopback"
            )
        if timeout_seconds <= 0:
            raise ValueError("embedding timeout must be positive")
        if not 0 <= max_retries <= 5:
            raise ValueError("embedding max_retries must be between 0 and 5")
        if retry_backoff_seconds < 0:
            raise ValueError("embedding retry backoff cannot be negative")
        if not 1 <= batch_size <= 256:
            raise ValueError("embedding batch_size must be between 1 and 256")
        if not 0 <= cache_size <= 4096:
            raise ValueError("embedding cache_size must be between 0 and 4096")
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required for the external embedding provider")
        self.manifest = EmbeddingManifest(
            provider="openai-embeddings",
            model=model_name,
            revision="api",
            dimension=dimension,
            metric="cosine",
            normalized=False,
        )
        self._api_key = key
        self._endpoint = f"{base_url.rstrip('/')}/embeddings"
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._batch_size = batch_size
        self._cache_size = cache_size
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_lock = RLock()
        self._cache_hits = 0
        self._cache_misses = 0

    @staticmethod
    def _cache_key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _cache_get(self, text: str) -> list[float] | None:
        if not self._cache_size:
            with self._cache_lock:
                self._cache_misses += 1
            return None
        key = self._cache_key(text)
        with self._cache_lock:
            vector = self._cache.get(key)
            if vector is None:
                self._cache_misses += 1
                return None
            self._cache_hits += 1
            self._cache.move_to_end(key)
            return list(vector)

    @property
    def cache_stats(self) -> dict[str, int]:
        """Return privacy-safe cache counters without exposing input text."""

        with self._cache_lock:
            return {
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "entries": len(self._cache),
                "capacity": self._cache_size,
            }

    def _cache_put(self, text: str, vector: list[float]) -> None:
        if not self._cache_size:
            return
        key = self._cache_key(text)
        with self._cache_lock:
            self._cache[key] = list(vector)
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

    def _request(self, inputs: Sequence[str]) -> list[list[float]]:
        if not inputs or any(not text.strip() for text in inputs):
            raise ValueError("embedding input cannot be empty")
        payload = json.dumps({"model": self.manifest.model, "input": list(inputs)}).encode()
        request = Request(
            self._endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        for attempt in range(self._max_retries + 1):
            try:
                with urlopen(request, timeout=self._timeout_seconds) as response:
                    raw_body = response.read(_MAX_RESPONSE_BYTES + 1)
                if len(raw_body) > _MAX_RESPONSE_BYTES:
                    raise RuntimeError("external embedding response exceeds the size limit")
                body = json.loads(raw_body.decode("utf-8"))
                break
            except HTTPError as error:
                retryable = error.code == 408 or error.code == 429 or error.code >= 500
                if not retryable or attempt == self._max_retries:
                    raise RuntimeError("external embedding request failed") from error
            except json.JSONDecodeError as error:
                raise RuntimeError("external embedding request returned invalid JSON") from error
            except (URLError, TimeoutError, OSError) as error:
                if attempt == self._max_retries:
                    raise RuntimeError("external embedding request failed") from error
            sleep(self._retry_backoff_seconds * (2**attempt))
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list) or len(data) != len(inputs):
            raise RuntimeError("external embedding response has an invalid shape")
        if any(
            not isinstance(item, dict)
            or isinstance(item.get("index"), bool)
            or not isinstance(item.get("index"), int)
            or not isinstance(item.get("embedding"), list)
            for item in data
        ):
            raise RuntimeError("external embedding response has invalid vectors")
        ordered = sorted(data, key=lambda item: item["index"])
        indexes = [item["index"] for item in ordered]
        if indexes != list(range(len(inputs))):
            raise RuntimeError("external embedding response has invalid indexes")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for item in ordered
            for value in item["embedding"]
        ):
            raise RuntimeError("external embedding response has invalid vectors")
        vectors = [
            [float(value) for value in item["embedding"]]
            for item in ordered
        ]
        if any(
            len(vector) != self.manifest.dimension
            or not all(isfinite(value) for value in vector)
            or sum(value * value for value in vector) == 0
            for vector in vectors
        ):
            raise ValueError("external embedding vector does not match manifest")
        return vectors

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            raise ValueError("embedding input cannot be empty")
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("embedding input cannot be empty")
        vectors: list[list[float] | None] = [self._cache_get(text) for text in texts]
        missing_positions: dict[str, list[int]] = {}
        missing_texts: list[str] = []
        for index, (text, vector) in enumerate(zip(texts, vectors)):
            if vector is None:
                key = self._cache_key(text)
                if key not in missing_positions:
                    missing_positions[key] = []
                    missing_texts.append(text)
                missing_positions[key].append(index)
        for start in range(0, len(missing_texts), self._batch_size):
            batch = missing_texts[start : start + self._batch_size]
            batch_vectors = self._request(batch)
            for offset, vector in enumerate(batch_vectors):
                text = batch[offset]
                for position in missing_positions[self._cache_key(text)]:
                    vectors[position] = list(vector)
                self._cache_put(text, vector)
        if any(vector is None for vector in vectors):
            raise RuntimeError("external embedding response did not cover every input")
        return [vector for vector in vectors if vector is not None]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
