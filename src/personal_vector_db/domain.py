"""Canonical document structures shared by parsers and later ingest stages."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    location: dict[str, object] = Field(default_factory=dict)
    heading_path: list[str] = Field(default_factory=list)


class CanonicalDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(pattern=r"^doc_[A-Za-z0-9_-]+$")
    source_uri: str = Field(min_length=1)
    source_type: Literal[
        "markdown", "text", "pdf", "docx", "html", "json", "jsonl", "yaml",
        "rtf", "csv", "email", "xml"
    ]
    title: str = ""
    owner_id: Literal["me"] = "me"
    visibility: Literal["private"] = "private"
    document_status: Literal["parsed", "failed", "needs_review"] = "parsed"
    content_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    parser_version: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    sections: list[Section] = Field(min_length=1)
