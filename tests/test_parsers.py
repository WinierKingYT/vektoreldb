import json
import sys
import zipfile
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from personal_vector_db.parsers import parse_source


def test_html_parser_keeps_visible_content_and_drops_chrome(tmp_path: Path) -> None:
    path = tmp_path / "page.html"
    path.write_text(
        "<title>Sayfa başlığı</title><nav>Menu</nav><main><h1>Başlık</h1><p>İçerik</p></main>"
        "<script>secret()</script><footer>Footer</footer>",
        encoding="utf-8",
    )

    document = parse_source(path)

    assert document.source_type == "html"
    assert document.parser_version == "html-v4"
    assert document.title == "Sayfa başlığı"
    assert [section.text for section in document.sections] == ["Başlık", "İçerik"]
    assert document.sections[1].heading_path == ["Başlık"]
    assert all("Menu" not in section.text for section in document.sections)
    assert all("secret" not in section.text for section in document.sections)


@pytest.mark.parametrize(
    "html",
    [
        "<nav>chrome</aside><p>still hidden</p></nav><p>Visible</p>",
        "<nav><aside>chrome</nav><p>Visible</p>",
    ],
)
def test_html_parser_recovers_ignored_stack_without_leaking_or_losing_text(
    tmp_path: Path, html: str
) -> None:
    path = tmp_path / "malformed.html"
    path.write_text(html, encoding="utf-8")

    document = parse_source(path)

    assert [section.text for section in document.sections] == ["Visible"]


def test_json_and_csv_parsers_are_deterministic(tmp_path: Path) -> None:
    json_path = tmp_path / "records.json"
    json_path.write_text(json.dumps([{"z": 1, "a": "iki"}], ensure_ascii=False), encoding="utf-8")
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("name,value\nAda,42\n", encoding="utf-8")

    json_document = parse_source(json_path)
    csv_document = parse_source(csv_path)

    assert json_document.sections[0].text == '{"a": "iki", "z": 1}'
    assert csv_document.sections[0].text == "name: Ada\nvalue: 42"
    assert csv_document.sections[0].location == {"row": 1}


def test_yaml_parser_is_safe_and_deterministic(tmp_path: Path) -> None:
    yaml_path = tmp_path / "settings.yaml"
    yaml_path.write_text(
        "items:\n  - name: Ada\n    enabled: true\n"
        "owner: me\n",
        encoding="utf-8",
    )

    document = parse_source(yaml_path)

    assert document.source_type == "yaml"
    assert document.parser_version == "yaml-v1"
    assert document.sections[0].text == (
        '{"items": [{"enabled": true, "name": "Ada"}], "owner": "me"}'
    )
    assert document.sections[0].location == {"record": 1}


def test_yaml_parser_rejects_python_object_construction(tmp_path: Path) -> None:
    yaml_path = tmp_path / "unsafe.yaml"
    yaml_path.write_text(
        "!!python/object/apply:os.system ['echo should-not-run']\n",
        encoding="utf-8",
    )

    with pytest.raises(yaml.YAMLError):
        parse_source(yaml_path)


def test_rtf_parser_extracts_text_and_unicode_without_interpreting_controls(
    tmp_path: Path,
) -> None:
    rtf_path = tmp_path / "note.rtf"
    rtf_text = r"{\rtf1\ansi Kisisel not\par Turk\u231?e \u199?\par \b kalin metin}"
    rtf_path.write_bytes(rtf_text.encode("cp1252"))

    document = parse_source(rtf_path)

    assert document.source_type == "rtf"
    assert document.parser_version == "rtf-v1"
    assert [section.text for section in document.sections] == [
        "Kisisel not",
        f"Turk{chr(231)}e {chr(199)}",
        "kalin metin",
    ]
    assert document.sections[1].location == {"format": "rtf", "index": 2}


def test_rtf_parser_rejects_non_rtf_payload(tmp_path: Path) -> None:
    rtf_path = tmp_path / "not-rtf.rtf"
    rtf_path.write_text("plain text", encoding="utf-8")

    with pytest.raises(ValueError, match="RTF header"):
        parse_source(rtf_path)


def test_rtf_parser_drops_nested_metadata_and_object_groups(tmp_path: Path) -> None:
    rtf_path = tmp_path / "rich-note.rtf"
    rtf_path.write_text(
        r"{\rtf1{\fonttbl{\f0 Arial;}}{\info{secret metadata}}"
        r"{\pict\bin1 hidden-image}\par Visible note}",
        encoding="ascii",
    )

    document = parse_source(rtf_path)

    assert [section.text for section in document.sections] == ["Visible note"]


def test_rtf_parser_rejects_unbalanced_groups(tmp_path: Path) -> None:
    rtf_path = tmp_path / "broken.rtf"
    rtf_path.write_text(r"{\rtf1 Broken", encoding="ascii")

    with pytest.raises(ValueError, match="unbalanced"):
        parse_source(rtf_path)


def test_structured_utf8_bom_exports_are_normalized(tmp_path: Path) -> None:
    json_path = tmp_path / "records.json"
    json_path.write_text('{"kind": "note"}', encoding="utf-8-sig")
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("name,value\nAda,42\n", encoding="utf-8-sig")
    html_path = tmp_path / "page.html"
    html_path.write_text("<p>İçerik</p>", encoding="utf-8-sig")

    json_document = parse_source(json_path)
    csv_document = parse_source(csv_path)
    html_document = parse_source(html_path)

    assert json_document.sections[0].text == '{"kind": "note"}'
    assert csv_document.sections[0].text == "name: Ada\nvalue: 42"
    assert html_document.sections[0].text == "İçerik"


def test_jsonl_parser_preserves_line_provenance(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "events.jsonl"
    jsonl_path.write_text(
        '{"z": 1, "a": "iki"}\n\n{"event": "üç"}\n', encoding="utf-8"
    )

    document = parse_source(jsonl_path)

    assert document.source_type == "jsonl"
    assert document.parser_version == "jsonl-v1"
    assert [section.location for section in document.sections] == [
        {"line": 1},
        {"line": 3},
    ]
    assert document.sections[0].text == '{"a": "iki", "z": 1}'
    assert document.sections[1].location == {"line": 3}


def test_jsonl_parser_fails_closed_on_invalid_line(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "broken.jsonl"
    jsonl_path.write_text('{"ok": true}\nnot-json\n', encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        parse_source(jsonl_path)


def test_ndjson_alias_uses_the_jsonl_contract(tmp_path: Path) -> None:
    ndjson_path = tmp_path / "events.ndjson"
    ndjson_path.write_text('{"event": "one"}\n', encoding="utf-8")

    document = parse_source(ndjson_path)

    assert document.source_type == "jsonl"
    assert document.parser_version == "jsonl-v1"
    assert document.sections[0].location == {"line": 1}


def test_xml_parser_extracts_leaf_text_with_locations(tmp_path: Path) -> None:
    xml_path = tmp_path / "export.xml"
    xml_path.write_text(
        "<export><entry><title>Bir not</title><body>İçerik</body></entry>"
        "<entry><title>İkinci not</title></entry></export>",
        encoding="utf-8",
    )

    document = parse_source(xml_path)

    assert document.source_type == "xml"
    assert document.parser_version == "xml-v1"
    assert [section.text for section in document.sections] == [
        "Bir not",
        "İçerik",
        "İkinci not",
    ]
    assert document.sections[0].location == {"format": "xml", "path": "/export/entry/title"}


def test_xml_parser_rejects_dtd_and_entity_declarations(tmp_path: Path) -> None:
    xml_path = tmp_path / "unsafe.xml"
    xml_path.write_text(
        '<!DOCTYPE export [<!ENTITY secret "hidden">]><export>&secret;</export>',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="DTD/entity"):
        parse_source(xml_path)


def test_email_parser_keeps_plain_body_and_ignores_attachments(tmp_path: Path) -> None:
    message = EmailMessage()
    message["Subject"] = "Kişisel proje notu"
    message["From"] = "me@example.test"
    message.set_content("İlk paragraf.\n\nİkinci paragraf.")
    message.add_attachment(
        b"attachment secret", maintype="application", subtype="octet-stream", filename="secret.bin"
    )
    path = tmp_path / "note.eml"
    path.write_bytes(bytes(message))

    document = parse_source(path)

    assert document.source_type == "email"
    assert document.parser_version == "email-v1"
    assert document.title == "Kişisel proje notu"
    assert [section.text for section in document.sections] == [
        "İlk paragraf.",
        "İkinci paragraf.",
    ]
    assert "attachment secret" not in " ".join(section.text for section in document.sections)


def test_docx_parser_preserves_paragraph_and_table_locations(tmp_path: Path) -> None:
    path = tmp_path / "notes.docx"
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>Paragraf</w:t></w:r></w:p>
        <w:tbl><w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
      </w:body>
    </w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)

    document = parse_source(path)

    assert [section.text for section in document.sections] == ["Paragraf", "A | B"]
    assert document.sections[0].location == {"paragraph": 1}
    assert document.sections[1].location == {"table": 1, "row": 1}


def test_docx_parser_preserves_tabs_and_explicit_line_breaks(tmp_path: Path) -> None:
    path = tmp_path / "spacing.docx"
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>Deniz</w:t><w:tab/><w:t>Kaya</w:t>
      <w:br/><w:t>İkinci satır</w:t><w:cr/><w:t>Üçüncü satır</w:t></w:r></w:p></w:body>
    </w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)

    document = parse_source(path)

    assert document.sections[0].text == "Deniz\tKaya\nİkinci satır\nÜçüncü satır"
    assert document.parser_version == "docx-v4"


def test_docx_table_cells_preserve_breaks_without_duplicating_nested_tables(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nested-table.docx"
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:tbl><w:tr><w:tc>
        <w:p><w:r><w:t>Dış</w:t><w:tab/><w:t>hücre</w:t><w:br/><w:t>devam</w:t></w:r></w:p>
        <w:tbl><w:tr><w:tc><w:p><w:r><w:t>İç tablo</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
      </w:tc></w:tr></w:tbl></w:body>
    </w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)

    document = parse_source(path)

    assert [section.text for section in document.sections] == [
        "Dış\thücre\ndevam",
        "İç tablo",
    ]
    assert document.sections[1].location == {"table": 1, "row": 2}


@pytest.mark.parametrize("unsafe_member", ["word/document.xml", "docProps/core.xml"])
@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_docx_parser_rejects_dtd_and_entity_declarations(
    tmp_path: Path, encoding: str, unsafe_member: str
) -> None:
    path = tmp_path / "unsafe-xml.docx"
    valid_document = """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>Güvenli metin</w:t></w:r></w:p></w:body></w:document>"""
    document_xml = (
        "<!DOCTYPE w:document [<!ENTITY local 'expanded'>]>"
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        "<w:body><w:p><w:r><w:t>&local;</w:t></w:r></w:p></w:body></w:document>"
        if unsafe_member == "word/document.xml"
        else valid_document
    )
    core_xml = (
        "<!DOCTYPE cp:coreProperties [<!ENTITY local 'expanded'>]>"
        "<cp:coreProperties "
        "xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties' "
        "xmlns:dc='http://purl.org/dc/elements/1.1/'><dc:title>&local;</dc:title></cp:coreProperties>"
        if unsafe_member == "docProps/core.xml"
        else None
    )
    with zipfile.ZipFile(path, "w") as archive:
        document_encoding = encoding if unsafe_member == "word/document.xml" else "utf-8"
        archive.writestr("word/document.xml", document_xml.encode(document_encoding))
        if core_xml is not None:
            archive.writestr(unsafe_member, core_xml.encode(encoding))

    with pytest.raises(ValueError, match="DOCX XML DTD/entity"):
        parse_source(path)


def test_docx_parser_preserves_heading_path(tmp_path: Path) -> None:
    path = tmp_path / "structured.docx"
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Bölüm</w:t></w:r></w:p>
        <w:p><w:r><w:t>Açıklama</w:t></w:r></w:p>
      </w:body>
    </w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
        archive.writestr(
            "docProps/core.xml",
            """<cp:coreProperties
              xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
              xmlns:dc="http://purl.org/dc/elements/1.1/">
              <dc:title>Yapılandırılmış notlar</dc:title>
            </cp:coreProperties>""",
        )

    document = parse_source(path)

    assert document.parser_version == "docx-v4"
    assert document.title == "Yapılandırılmış notlar"
    assert document.sections[1].heading_path == ["Bölüm"]


def test_docx_parser_rejects_unsafe_archive_member_paths(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("../outside.txt", "must not be extracted")
        archive.writestr("word/document.xml", "<w:document/>")

    with pytest.raises(ValueError, match="unsafe member path"):
        parse_source(path)


def test_docx_parser_rejects_windows_style_archive_member_paths(tmp_path: Path) -> None:
    path = tmp_path / "unsafe-windows.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(r"C:\outside.txt", "must not be extracted")
        archive.writestr("word/document.xml", "<w:document/>")

    with pytest.raises(ValueError, match="unsafe member path"):
        parse_source(path)


def test_docx_parser_rejects_duplicate_archive_member_names(tmp_path: Path) -> None:
    path = tmp_path / "duplicate-members.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", "<w:document/>")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("word/document.xml", "<w:document><w:body/></w:document>")

    with pytest.raises(ValueError, match="duplicate member names"):
        parse_source(path)


def test_pdf_parser_extracts_nonempty_pages_with_locations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class FakePdfReader:
        def __init__(self, _path: str) -> None:
            self.pages = [FakePage("Birinci sayfa"), FakePage(""), FakePage("Üçüncü")]
            self.metadata = SimpleNamespace(title="PDF rapor başlığı")
            self.is_encrypted = False

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=FakePdfReader))
    path = tmp_path / "report.pdf"
    path.write_bytes(b"mock pdf")

    document = parse_source(path)

    assert document.source_type == "pdf"
    assert document.parser_version == "pdf-v2"
    assert document.title == "PDF rapor başlığı"
    assert [section.text for section in document.sections] == ["Birinci sayfa", "Üçüncü"]
    assert [section.location for section in document.sections] == [{"page": 1}, {"page": 3}]


def test_pdf_parser_extracts_text_from_a_real_minimal_pdf(tmp_path: Path) -> None:
    text = "Personal PDF note"
    stream = f"BT /F1 12 Tf 36 250 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    path = tmp_path / "minimal-real.pdf"
    path.write_bytes(pdf)

    document = parse_source(path)

    assert document.source_type == "pdf"
    assert document.parser_version == "pdf-v2"
    assert [section.text for section in document.sections] == [text]
    assert document.sections[0].location == {"page": 1}


def test_pdf_parser_rejects_encrypted_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class EncryptedPdfReader:
        is_encrypted = True

        def __init__(self, _path: str) -> None:
            self.pages = []

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=EncryptedPdfReader))
    path = tmp_path / "encrypted.pdf"
    path.write_bytes(b"mock pdf")

    with pytest.raises(ValueError, match="encrypted PDF"):
        parse_source(path)


def test_parser_rejects_unknown_suffix(tmp_path: Path) -> None:
    path = tmp_path / "data.exe"
    path.write_bytes(b"not a document")

    with pytest.raises(ValueError, match="unsupported source format"):
        parse_source(path)


@pytest.mark.parametrize("suffix", [".org", ".rst", ".log", ".tex", ".ics"])
def test_personal_plain_text_aliases_use_canonical_text_parser(
    tmp_path: Path, suffix: str
) -> None:
    path = tmp_path / f"notes{suffix}"
    path.write_text("personal note\nsecond line", encoding="utf-8")

    document = parse_source(path)

    assert document.source_type == "text"
    assert document.parser_version == "plain-text-v1"
    assert [section.text for section in document.sections] == ["personal note\nsecond line"]


def test_parser_applies_size_limit_to_direct_calls(tmp_path: Path) -> None:
    path = tmp_path / "large.md"
    path.write_text("12345", encoding="utf-8")

    with pytest.raises(ValueError, match="size limit"):
        parse_source(path, max_bytes=4)
