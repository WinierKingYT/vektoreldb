"""Input and local-source safety checks for personal ingestion."""

import re
from pathlib import Path

SUPPORTED_SUFFIXES = frozenset(
    {
        ".md", ".markdown", ".txt", ".org", ".rst", ".log", ".tex", ".ics",
        ".pdf", ".docx", ".html", ".htm",
        ".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".rtf", ".csv", ".eml", ".xml",
    }
)

DEFAULT_EXCLUDED_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
        "__pycache__", ".cache", "cache", "caches", "tmp", "temp", "build", "dist",
        "secret", "secrets", "credential", "credentials",
    }
)


def is_excluded_directory(path: Path, root: Path) -> bool:
    """Return whether a recursive source path is under a default excluded directory."""

    relative_parts = path.relative_to(root).parts
    return any(part.casefold() in DEFAULT_EXCLUDED_DIRS for part in relative_parts)

_PROMPT_INJECTION_PATTERNS = (
    ("instruction_override", re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I)),
    ("instruction_override_tr", re.compile(r"önceki\s+talimatları\s+yok\s+say", re.I)),
    ("secret_exfiltration", re.compile(r"reveal\s+(the\s+)?system\s+prompt", re.I)),
    ("command_execution", re.compile(r"execute\s+(this\s+)?command", re.I)),
)


def detect_prompt_injection(text: str) -> tuple[str, ...]:
    """Return stable red-team flags without logging or returning source text."""

    return tuple(name for name, pattern in _PROMPT_INJECTION_PATTERNS if pattern.search(text))


def validate_source_path(path: Path, source_root: Path, *, max_bytes: int = 10_000_000) -> Path:
    """Resolve and validate a source path before reading it."""

    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    resolved_root = source_root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError("source path is outside the configured source root") from error
    if not resolved_path.is_file():
        raise ValueError("source path is not a file")
    if resolved_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("unsupported source format")
    if resolved_path.stat().st_size > max_bytes:
        raise ValueError("source file exceeds the configured size limit")
    return resolved_path
