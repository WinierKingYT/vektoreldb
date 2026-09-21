"""Source parsers with explicit format dispatch."""

from pathlib import Path

from personal_vector_db.security import SUPPORTED_SUFFIXES

from .plain_text import parse_text_file
from .rich import parse_source_file


def parse_source(path: Path, *, max_bytes: int = 10_000_000):
    """Parse a supported source or fail explicitly for unknown formats."""

    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported source format: {path.suffix or '<none>'}")
    return parse_source_file(path, max_bytes=max_bytes)


__all__ = ["SUPPORTED_SUFFIXES", "parse_source", "parse_source_file", "parse_text_file"]
