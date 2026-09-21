"""Deterministic plain-text parser with optional Markdown heading handling."""

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from personal_vector_db.domain import CanonicalDocument, Section

PARSER_VERSION = "plain-text-v1"
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def _decode_text(raw: bytes) -> str:
    """Decode common Unicode BOMs without weakening malformed UTF-8 handling."""

    if raw.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return raw.decode("utf-32")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def parse_text_file(path: Path, *, max_bytes: int = 10_000_000) -> CanonicalDocument:
    """Parse UTF-8 Markdown/TXT while retaining heading paths and line locations."""

    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    if not path.is_file():
        raise ValueError("source path is not a file")
    if path.stat().st_size > max_bytes:
        raise ValueError("source file exceeds the configured size limit")
    raw = path.read_bytes()
    content_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    text = _normalize(_decode_text(raw))
    if not text:
        raise ValueError(f"empty text file: {path}")

    suffix = path.suffix.lower()
    source_type = "markdown" if suffix in {".md", ".markdown"} else "text"
    headings: list[str] = []
    sections: list[Section] = []
    buffer: list[str] = []
    start_line = 1

    def flush(end_line: int) -> None:
        if not buffer:
            return
        section_text = "\n".join(buffer).strip()
        if section_text:
            sections.append(
                Section(
                    text=section_text,
                    heading_path=headings.copy(),
                    location={"start_line": start_line, "end_line": end_line},
                )
            )

    for line_number, line in enumerate(text.splitlines(), start=1):
        match = _HEADING.match(line) if source_type == "markdown" else None
        if match:
            flush(line_number - 1)
            level = len(match.group(1))
            headings = headings[: level - 1] + [match.group(2)]
            buffer.clear()
            start_line = line_number
        else:
            if not buffer and not line.strip():
                continue
            if not buffer:
                start_line = line_number
            buffer.append(line)
    flush(len(text.splitlines()))

    now = datetime.now(UTC)
    document_id = f"doc_{hashlib.sha256(str(path.resolve()).encode()).hexdigest()}"
    return CanonicalDocument(
        document_id=document_id,
        source_uri=path.resolve().as_uri(),
        source_type=source_type,
        title=path.stem,
        content_hash=content_hash,
        parser_version=PARSER_VERSION,
        created_at=now,
        updated_at=now,
        sections=sections,
    )
