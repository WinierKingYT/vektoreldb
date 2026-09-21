"""Deterministic hashed lexical vectors for the V1.2 hybrid experiment."""

import hashlib
import re
from collections import Counter

from qdrant_client.http import models


class SparseLexicalEncoder:
    """Encode normalized tokens as a collision-tolerant sparse vector."""

    version = "hashed-lexical-v1"
    bucket_count = 1_048_576
    _token_pattern = re.compile(r"(?u)\w+")

    @property
    def manifest_id(self) -> str:
        return f"{self.version}:buckets={self.bucket_count}"

    def encode(self, text: str) -> models.SparseVector:
        if not text.strip():
            raise ValueError("sparse embedding input cannot be empty")
        counts: Counter[int] = Counter()
        for token in self._token_pattern.findall(text.casefold()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest, "big") % self.bucket_count
            counts[bucket] += 1
        if not counts:
            raise ValueError("sparse embedding input has no tokens")
        norm = sum(value * value for value in counts.values()) ** 0.5
        indices = sorted(counts)
        return models.SparseVector(
            indices=indices,
            values=[counts[index] / norm for index in indices],
        )
