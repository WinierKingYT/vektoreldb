"""Deterministic token-level vectors for the V1.5 late-interaction experiment."""

import hashlib
import re
from math import sqrt


class LateInteractionEncoder:
    """Create bounded token vectors consumed by Qdrant MAX_SIM."""

    version = "hashed-late-v1"
    dimension = 32
    max_tokens = 128
    _token_pattern = re.compile(r"(?u)\w+")

    @property
    def manifest_id(self) -> str:
        return f"{self.version}:dim={self.dimension}:max_tokens={self.max_tokens}"

    def encode(self, text: str) -> list[list[float]]:
        tokens = self._token_pattern.findall(text.casefold())[: self.max_tokens]
        if not tokens:
            raise ValueError("late-interaction input has no tokens")
        vectors = []
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=self.dimension).digest()
            raw = [((byte / 255.0) * 2.0) - 1.0 for byte in digest]
            norm = sqrt(sum(value * value for value in raw))
            vectors.append([value / norm for value in raw])
        return vectors
