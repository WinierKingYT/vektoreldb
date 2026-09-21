"""Deterministic, structure-preserving chunking for the first text formats."""

import hashlib
import re
from dataclasses import dataclass

from personal_vector_db.domain import CanonicalDocument, Section

CHUNKING_VERSION = "paragraph-pack-v2"
_PARAGRAPH = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class Chunk:
    document_id: str
    chunk_id: str
    chunk_index: int
    text: str
    heading_path: tuple[str, ...]
    location: dict[str, object]
    token_count: int
    chunking_version: str = CHUNKING_VERSION


def _approx_tokens(text: str) -> int:
    """Use whitespace tokens until a model tokenizer is selected."""

    return len(text.split())


def _paragraphs(section: Section) -> list[str]:
    return [part.strip() for part in _PARAGRAPH.split(section.text) if part.strip()]


def chunk_document(
    document: CanonicalDocument,
    *,
    max_tokens: int = 600,
    overlap_tokens: int = 60,
) -> list[Chunk]:
    """Pack whole paragraphs and carry a bounded tail into the next chunk.

    The limits are approximate until the selected embedding model's tokenizer is
    wired in. A paragraph larger than the limit remains intact to avoid silently
    cutting structured content.
    """

    if max_tokens < 1 or overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("require 1 <= max_tokens and 0 <= overlap_tokens < max_tokens")

    chunks: list[Chunk] = []
    pending: list[tuple[str, Section]] = []

    def emit(items: list[tuple[str, Section]]) -> None:
        if not items:
            return
        text = "\n\n".join(part for part, _ in items)
        index = len(chunks)
        digest = hashlib.sha256(f"{document.document_id}:{index}:{text}".encode()).hexdigest()[:16]
        locations = [section.location for _, section in items]
        chunks.append(
            Chunk(
                document_id=document.document_id,
                chunk_id=f"{document.document_id}_chunk_{digest}",
                chunk_index=index,
                text=text,
                heading_path=items[-1][1].heading_path and tuple(items[-1][1].heading_path) or (),
                location={"parts": locations},
                token_count=_approx_tokens(text),
            )
        )

    for section in document.sections:
        for paragraph in _paragraphs(section):
            if pending and pending[-1][1].heading_path != section.heading_path:
                emit(pending)
                pending = []
            candidate = pending + [(paragraph, section)]
            if pending and _approx_tokens("\n\n".join(part for part, _ in candidate)) > max_tokens:
                emit(pending)
                tail: list[tuple[str, Section]] = []
                tail_tokens = 0
                for item in reversed(pending):
                    item_tokens = _approx_tokens(item[0])
                    if tail_tokens + item_tokens > overlap_tokens:
                        break
                    tail.insert(0, item)
                    tail_tokens += item_tokens
                pending = tail + [(paragraph, section)]
            else:
                pending = candidate
    emit(pending)
    return chunks
