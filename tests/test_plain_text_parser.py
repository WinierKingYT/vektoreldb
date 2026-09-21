from pathlib import Path

import pytest

from personal_vector_db.parsers import parse_text_file


def test_markdown_parser_preserves_heading_path_and_identity(tmp_path: Path) -> None:
    path = tmp_path / "notlar.md"
    path.write_text("# Ana\n\nİlk bölüm.\n\n## Alt\n\nİkinci bölüm.\n", encoding="utf-8")

    document = parse_text_file(path)

    assert document.source_type == "markdown"
    assert document.document_id.startswith("doc_")
    assert document.sections[0].heading_path == ["Ana"]
    assert document.sections[1].heading_path == ["Ana", "Alt"]
    assert document.sections[0].location["start_line"] == 3


def test_parser_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("\n", encoding="utf-8")

    try:
        parse_text_file(path)
    except ValueError as error:
        assert "empty" in str(error)
    else:
        raise AssertionError("empty files must be rejected")


def test_direct_text_parser_applies_size_limit(tmp_path: Path) -> None:
    path = tmp_path / "large.txt"
    path.write_text("12345", encoding="utf-8")

    with pytest.raises(ValueError, match="size limit"):
        parse_text_file(path, max_bytes=4)


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-32"])
def test_plain_text_parser_decodes_unicode_bom_exports(tmp_path: Path, encoding: str) -> None:
    path = tmp_path / "export.txt"
    path.write_text("Başlık\nİçerik", encoding=encoding)

    document = parse_text_file(path)

    assert [section.text for section in document.sections] == ["Başlık\nİçerik"]
