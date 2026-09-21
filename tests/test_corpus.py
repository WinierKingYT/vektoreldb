import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from personal_vector_db.corpus import (
    count_excluded_files,
    inventory_sources,
    read_corpus_manifest,
    summarize_unsupported_files,
    write_corpus_inventory,
    write_corpus_manifest,
)


def test_inventory_isolates_oversized_source_without_reading_it(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "ok.md").write_text("small", encoding="utf-8")
    oversized = root / "too-large.md"
    oversized.write_bytes(b"x" * 10_000_001)

    records = inventory_sources(root)

    by_path = {record["relative_path"]: record for record in records}
    assert by_path["ok.md"]["status"] == "parsed"
    assert by_path["ok.md"]["chunk_ids"]
    assert by_path["too-large.md"]["status"] == "failed"
    assert by_path["too-large.md"]["error_type"] == "ValueError"
    assert by_path["too-large.md"]["content_hash"] is None


def test_repository_corpus_covers_multiple_formats_and_medium_bucket() -> None:
    records = inventory_sources(Path("data/sources"))

    suffixes = {str(record["suffix"]) for record in records}
    assert {
        ".md", ".html", ".json", ".jsonl", ".csv", ".eml", ".ics", ".org", ".rtf", ".xml"
    } <= suffixes
    assert any(record["size_bucket"] == "medium" for record in records)
    assert all(record["status"] == "parsed" for record in records)


def test_inventory_dispatches_pdf_docx_and_html_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakePage:
        def extract_text(self) -> str:
            return "PDF inventory evidence"

    class FakePdfReader:
        def __init__(self, _path: str) -> None:
            self.pages = [FakePage()]
            self.metadata = SimpleNamespace(title="Inventory PDF")
            self.is_encrypted = False

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=FakePdfReader))
    root = tmp_path / "sources"
    root.mkdir()
    (root / "page.html").write_text(
        "<html><body><h1>Inventory HTML</h1><p>Visible content</p></body></html>",
        encoding="utf-8",
    )
    (root / "report.pdf").write_bytes(b"synthetic pdf")
    with zipfile.ZipFile(root / "notes.docx", "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Inventory DOCX</w:t></w:r></w:p></w:body>"
            "</w:document>",
        )

    records = inventory_sources(root)

    by_suffix = {record["suffix"]: record for record in records}
    assert by_suffix[".pdf"]["status"] == "parsed"
    assert by_suffix[".pdf"]["parser_version"] == "pdf-v2"
    assert by_suffix[".docx"]["status"] == "parsed"
    assert by_suffix[".docx"]["parser_version"] == "docx-v4"
    assert by_suffix[".html"]["status"] == "parsed"
    assert by_suffix[".html"]["parser_version"] == "html-v4"


def test_inventory_classifies_a_large_source_without_reading_source_text(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    large = root / "large.md"
    large.write_bytes(b"x" * 1_000_000)

    records = inventory_sources(root)

    assert records[0]["size_bucket"] == "large"
    assert records[0]["status"] == "parsed"


def test_inventory_file_limit_rejects_before_parsing_or_writing(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "a.md").write_text("first", encoding="utf-8")
    (root / "b.md").write_text("second", encoding="utf-8")
    output = tmp_path / "inventory.json"

    with pytest.raises(ValueError, match="source file limit"):
        write_corpus_inventory(root, output, max_files=1)

    assert not output.exists()


def test_inventory_total_bytes_limit_rejects_before_parsing_or_writing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "a.md").write_text("first", encoding="utf-8")
    (root / "b.md").write_text("second", encoding="utf-8")
    output = tmp_path / "inventory.json"

    with pytest.raises(ValueError, match="total source bytes limit"):
        write_corpus_inventory(root, output, max_total_bytes=10)

    assert not output.exists()


def test_inventory_includes_exact_total_bytes_boundary(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "note.md").write_text("12345", encoding="utf-8")

    records = inventory_sources(root, max_total_bytes=5)

    assert len(records) == 1
    assert records[0]["status"] == "parsed"


def test_inventory_surfaces_successful_but_empty_extraction(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "script-only.html").write_text(
        "<html><script>const privateValue = 1;</script></html>", encoding="utf-8"
    )

    records = inventory_sources(root)
    manifest = write_corpus_manifest(root, records, tmp_path / "manifest.json")

    assert records[0]["status"] == "failed"
    assert records[0]["extraction_status"] == "empty"
    assert manifest["empty_extraction_count"] == 1


def test_inventory_excludes_default_sensitive_and_build_directories(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "keep.md").write_text("keep", encoding="utf-8")
    for directory in (".git", "secrets", "cache", "build"):
        hidden = root / directory
        hidden.mkdir()
        (hidden / "hidden.json").write_text('{"secret": true}', encoding="utf-8")

    records = inventory_sources(root)

    assert [record["relative_path"] for record in records] == ["keep.md"]
    assert count_excluded_files(root) == 4


def test_summarize_unsupported_files_is_privacy_safe_and_excludes_hidden_dirs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "photo.png").write_bytes(b"not indexed")
    (root / "README").write_text("no suffix", encoding="utf-8")
    hidden = root / "cache"
    hidden.mkdir()
    (hidden / "ignored.png").write_bytes(b"ignored")

    assert summarize_unsupported_files(root) == {"<none>": 1, ".png": 1}


def test_corpus_manifest_accepts_failed_inventory_records(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    path = root / "broken.md"
    path.write_bytes(b"x" * 10_000_001)
    output = tmp_path / "manifest.json"

    records = inventory_sources(root)
    manifest = write_corpus_manifest(root, records, output)

    assert manifest["source_count"] == 1
    assert manifest["parsed_source_count"] == 0
    assert manifest["failed_source_count"] == 1
    assert manifest["chunk_ids"] == []
    assert manifest["failure_types"] == {"ValueError": 1}


def test_corpus_manifest_records_source_size_bucket_counts(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "small.md").write_text("small", encoding="utf-8")
    medium = root / "medium.md"
    medium.write_bytes(b"m" * 10_000)
    large = root / "large.md"
    large.write_bytes(b"l" * 1_000_000)

    manifest = write_corpus_manifest(
        root, inventory_sources(root), tmp_path / "manifest.json"
    )

    assert manifest["size_bucket_counts"] == {
        "large": 1,
        "medium": 1,
        "small": 1,
    }
    assert len(manifest["chunk_size_buckets"]) == manifest["total_chunks"]


def test_corpus_manifest_round_trip_is_validated(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "note.md").write_text("# Başlık\n\nİçerik", encoding="utf-8")
    output = tmp_path / "manifest.json"

    manifest = write_corpus_manifest(root, inventory_sources(root), output)

    assert read_corpus_manifest(output) == manifest


def test_corpus_manifest_without_optional_summaries_remains_compatible(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    output = tmp_path / "manifest.json"
    manifest = write_corpus_manifest(
        root,
        [
            {
                "relative_path": "old.md",
                "suffix": ".md",
                "content_hash": "sha256:" + "a" * 64,
                "status": "failed",
                "byte_size": 1,
                "chunk_count": 0,
            }
        ],
        output,
    )
    legacy = {
        key: value
        for key, value in manifest.items()
        if key not in {"format_counts", "failure_types", "duplicate_count", "total_extracted_chars"}
    }
    output.write_text(json.dumps(legacy), encoding="utf-8")

    assert read_corpus_manifest(output) == legacy


def test_inventory_surfaces_duplicate_bytes_without_merging_sources(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    (root / "backup").mkdir(parents=True)
    (root / "note.md").write_text("same content", encoding="utf-8")
    (root / "backup" / "note-copy.md").write_text("same content", encoding="utf-8")

    records = inventory_sources(root)

    by_path = {record["relative_path"]: record for record in records}
    assert by_path["note.md"]["duplicate_of"] is None
    assert by_path["backup/note-copy.md"]["duplicate_of"] == "note.md"
    # Both files remain parseable inputs; duplicate detection is advisory.
    assert by_path["note.md"]["status"] == "parsed"
    assert by_path["backup/note-copy.md"]["status"] == "parsed"


def test_inventory_includes_jsonl_parser_and_manifest_provenance(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "events.jsonl").write_text(
        '{"kind": "one"}\n{"kind": "two"}\n', encoding="utf-8"
    )

    records = inventory_sources(root)
    manifest = write_corpus_manifest(root, records, tmp_path / "manifest.json")

    record = records[0]
    assert record["source_type"] == "jsonl"
    assert record["parser_version"] == "jsonl-v1"
    assert record["chunk_ids"]
    assert record["extracted_char_count"] > 0
    assert record["nonempty_section_count"] == record["section_count"]
    assert manifest["parser_versions"] == ["jsonl-v1"]
    assert manifest["total_chunks"] == record["chunk_count"]
    assert manifest["total_extracted_chars"] == record["extracted_char_count"]


def test_corpus_manifest_persists_format_failure_and_duplicate_summary(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    (root / "note.md").write_text("note", encoding="utf-8")
    events = root / "events.jsonl"
    events.write_text('{"kind": "one"}\n', encoding="utf-8")
    (root / "events-copy.jsonl").write_bytes(events.read_bytes())

    records = inventory_sources(root)
    manifest = write_corpus_manifest(root, records, tmp_path / "manifest.json")

    assert manifest["format_counts"] == {".jsonl": 2, ".md": 1}
    assert manifest["failure_types"] == {}
    assert manifest["duplicate_count"] == 1
