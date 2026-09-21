"""Runtime validation against the repository's canonical JSON Schemas."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

PACKAGE_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
REPOSITORY_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
SCHEMA_DIR = PACKAGE_SCHEMA_DIR if PACKAGE_SCHEMA_DIR.is_dir() else REPOSITORY_SCHEMA_DIR


def validate_schema(document: dict[str, Any], schema_name: str) -> None:
    schema_path = SCHEMA_DIR / schema_name
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document), key=lambda error: error.path
    )
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "root"
        raise ValueError(f"schema validation failed at {location}: {errors[0].message}")
