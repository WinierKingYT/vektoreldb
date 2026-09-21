from pathlib import Path

from personal_vector_db.chunking import CHUNKING_VERSION, chunk_document
from personal_vector_db.parsers import parse_text_file


def test_chunking_is_deterministic_and_preserves_provenance(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    path.write_text(
        "# Başlangıç\n\nBir iki üç.\n\nDört beş altı.\n\n## İleri\n\nYedi sekiz dokuz.",
        encoding="utf-8",
    )
    document = parse_text_file(path)

    first = chunk_document(document, max_tokens=5, overlap_tokens=1)
    second = chunk_document(document, max_tokens=5, overlap_tokens=1)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert first[0].document_id == document.document_id
    assert first[0].chunking_version == CHUNKING_VERSION
    assert first[0].location["parts"]


def test_large_paragraph_is_not_silently_cut(tmp_path: Path) -> None:
    path = tmp_path / "long.txt"
    path.write_text("bir iki üç dört beş altı yedi", encoding="utf-8")
    document = parse_text_file(path)

    chunks = chunk_document(document, max_tokens=3, overlap_tokens=1)

    assert len(chunks) == 1
    assert chunks[0].text == "bir iki üç dört beş altı yedi"


def test_chunking_does_not_merge_different_heading_paths(tmp_path: Path) -> None:
    path = tmp_path / "sections.md"
    path.write_text(
        "# Birinci\n\nİlk içerik.\n\n# İkinci\n\nİkinci içerik.",
        encoding="utf-8",
    )
    document = parse_text_file(path)

    chunks = chunk_document(document, max_tokens=100, overlap_tokens=1)

    assert [chunk.heading_path for chunk in chunks] == [("Birinci",), ("İkinci",)]
