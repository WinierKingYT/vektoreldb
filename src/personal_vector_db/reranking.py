"""Opt-in candidate reranking providers."""

import re
from collections.abc import Sequence
from math import isfinite
from typing import Protocol


class Reranker(Protocol):
    name: str

    def score(self, query: str, texts: Sequence[str]) -> list[float]: ...


class LexicalOverlapReranker:
    """Deterministic, offline control reranker for V1.3 experiments."""

    name = "lexical-overlap-v1"
    _token_pattern = re.compile(r"(?u)\w+")

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        query_tokens = set(self._token_pattern.findall(query.casefold()))
        if not query_tokens:
            raise ValueError("reranker query has no tokens")
        scores = []
        for text in texts:
            tokens = set(self._token_pattern.findall(text.casefold()))
            union = query_tokens | tokens
            scores.append(len(query_tokens & tokens) / len(union) if union else 0.0)
        return scores

    def score_results(self, query: str, results: Sequence[object]) -> list[float]:
        """Score text plus safe document identity metadata for local reranking.

        Exact-identifier queries often name a heading or source file rather than
        repeating the chunk body. Metadata is already returned by retrieval and
        is therefore useful for this opt-in local control reranker without
        changing the stored embedding or the RAG evidence text.
        """
        enriched = []
        for result in results:
            heading_path = getattr(result, "heading_path", ()) or ()
            enriched.append(
                "\n".join(
                    (
                        str(getattr(result, "text", "")),
                        str(getattr(result, "title", "")),
                        str(getattr(result, "source_uri", "")),
                        " ".join(str(item) for item in heading_path),
                    )
                )
            )
        return self.score(query, enriched)


class LocalCrossEncoderReranker:
    """Lazy local Sentence Transformers CrossEncoder adapter."""

    name = "local-cross-encoder"

    def __init__(
        self,
        model_name: str,
        *,
        revision: str | None = None,
        model: object | None = None,
    ) -> None:
        self.model_name = model_name
        self.revision = revision
        self._model = model

    def _get_model(self) -> object:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            kwargs = {} if self.revision is None else {"revision": self.revision}
            self._model = CrossEncoder(self.model_name, **kwargs)
        return self._model

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        pairs = [[query, text] for text in texts]
        raw = self._get_model().predict(pairs)
        scores = [float(value) for value in raw]
        if len(scores) != len(texts) or not all(isfinite(value) for value in scores):
            raise ValueError("reranker returned invalid scores")
        return scores
