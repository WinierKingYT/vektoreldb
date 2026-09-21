"""Deterministic parsers for structured personal document formats."""

import csv
import hashlib
import io
import json
import re
import stat
import zipfile
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

import yaml

from personal_vector_db.domain import CanonicalDocument, Section
from personal_vector_db.parsers.plain_text import parse_text_file

_SUPPORTED_TEXT = {".md", ".markdown", ".txt", ".org", ".rst", ".log", ".tex", ".ics"}
_DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MAX_DOCX_UNCOMPRESSED_BYTES = 50_000_000
_MAX_PDF_EXTRACTED_CHARS = 50_000_000
_XML_FORBIDDEN_DECLARATIONS = ("<!doctype", "<!entity")
_RTF_HEX_ESCAPE = re.compile(r"\\'([0-9a-fA-F]{2})")
_RTF_UNICODE_ESCAPE = re.compile(r"\\u(-?\d+)\??")
_RTF_CONTROL_WORD = re.compile(r"\\[a-zA-Z]+-?\d* ?")
_XML_FORBIDDEN_BYTE_PATTERN = re.compile(rb"<!doctype|<!entity", re.IGNORECASE)
_RTF_IGNORED_DESTINATIONS = frozenset(
    {
        "colortbl",
        "datastore",
        "filetbl",
        "fonttbl",
        "footer",
        "header",
        "info",
        "object",
        "pict",
        "stylesheet",
        "themedata",
    }
)


def _read_utf8_text(path: Path) -> str:
    """Read structured UTF-8 exports while discarding an optional BOM."""

    return path.read_bytes().decode("utf-8-sig")


def _document(
    path: Path,
    source_type: str,
    sections: list[Section],
    *,
    parser_version: str | None = None,
    title: str | None = None,
) -> CanonicalDocument:
    if not sections:
        raise ValueError(f"empty parsed document: {path}")
    raw = path.read_bytes()
    now = datetime.now(UTC)
    return CanonicalDocument(
        document_id=f"doc_{hashlib.sha256(str(path.resolve()).encode()).hexdigest()}",
        source_uri=path.resolve().as_uri(),
        source_type=source_type,
        title=title or path.stem,
        content_hash=f"sha256:{hashlib.sha256(raw).hexdigest()}",
        parser_version=parser_version or f"{source_type}-v1",
        created_at=now,
        updated_at=now,
        sections=sections,
    )


def _docx_paragraph_text(paragraph: ElementTree.Element) -> str:
    """Preserve Word run boundaries represented as tabs and explicit breaks."""

    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{_DOCX_NS}t":
            parts.append(node.text or "")
        elif node.tag == f"{_DOCX_NS}tab":
            parts.append("\t")
        elif node.tag in {f"{_DOCX_NS}br", f"{_DOCX_NS}cr"}:
            parts.append("\n")
    return "".join(parts).strip()


def _docx_cell_text(cell: ElementTree.Element) -> str:
    """Join a cell's paragraphs without absorbing nested-table content twice."""

    paragraphs: list[str] = []

    def collect(node: ElementTree.Element) -> None:
        for child in node:
            if child.tag == f"{_DOCX_NS}tbl":
                continue
            if child.tag == f"{_DOCX_NS}p":
                text = _docx_paragraph_text(child)
                if text:
                    paragraphs.append(text)
                continue
            collect(child)

    collect(cell)
    return " ".join(paragraphs).strip()


def _parse_docx_xml(payload: bytes) -> ElementTree.Element:
    """Reject DTD/entity declarations before handing package XML to Expat."""

    has_forbidden_declaration = _XML_FORBIDDEN_BYTE_PATTERN.search(payload) is not None
    if not has_forbidden_declaration and b"\x00" in payload:
        utf16_ascii = payload.replace(b"\x00", b"")
        has_forbidden_declaration = _XML_FORBIDDEN_BYTE_PATTERN.search(utf16_ascii) is not None
    if has_forbidden_declaration:
        raise ValueError("DOCX XML DTD/entity declarations are not supported")
    return ElementTree.fromstring(payload)


class _VisibleHTML(HTMLParser):
    _ignored = {"script", "style", "nav", "footer", "header", "aside"}
    _blocks = {"p", "div", "li", "pre", "blockquote", "br"} | {
        f"h{level}" for level in range(1, 7)
    }

    def __init__(self) -> None:
        super().__init__()
        self.sections: list[tuple[str, str, list[str]]] = []
        self._current: list[str] = []
        self._current_tag = "body"
        self._heading_path: list[str] = []
        self._title_parts: list[str] = []
        self._in_title = False
        self._ignored_stack: list[str] = []
        self._ignored_counts: dict[str, int] = {}

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._ignored:
            self._ignored_stack.append(tag)
            self._ignored_counts[tag] = self._ignored_counts.get(tag, 0) + 1
            return
        if not self._ignored_stack and tag == "title":
            self._in_title = True
            return
        if not self._ignored_stack and tag in self._blocks:
            self._flush()
            self._current_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in self._ignored:
            if self._ignored_counts.get(tag, 0):
                matching_index = len(self._ignored_stack) - 1 - self._ignored_stack[::-1].index(tag)
                removed_tags = self._ignored_stack[matching_index:]
                del self._ignored_stack[matching_index:]
                for removed_tag in removed_tags:
                    remaining = self._ignored_counts[removed_tag] - 1
                    if remaining:
                        self._ignored_counts[removed_tag] = remaining
                    else:
                        del self._ignored_counts[removed_tag]
        elif tag == "title" and self._in_title:
            self._in_title = False
        elif not self._ignored_stack and tag in self._blocks:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._ignored_stack and data.strip():
            if self._in_title:
                self._title_parts.append(data.strip())
            else:
                self._current.append(data.strip())

    def _flush(self) -> None:
        text = " ".join(self._current).strip()
        if not text:
            return
        self.sections.append((text, self._current_tag, list(self._heading_path)))
        if self._current_tag.startswith("h") and self._current_tag[1:].isdigit():
            level = int(self._current_tag[1:])
            self._heading_path = self._heading_path[: level - 1] + [text]
        self._current = []

    def finish(self) -> list[tuple[str, str, list[str]]]:
        self._flush()
        return self.sections

    @property
    def title(self) -> str:
        return " ".join(self._title_parts).strip()


def _parse_html(path: Path) -> CanonicalDocument:
    parser = _VisibleHTML()
    parser.feed(_read_utf8_text(path))
    sections = [
        Section(
            text=text,
            location={"format": "html", "tag": tag, "index": index},
            heading_path=heading_path,
        )
        for index, (text, tag, heading_path) in enumerate(parser.finish())
    ]
    return _document(
        path,
        "html",
        sections,
        parser_version="html-v4",
        title=parser.title,
    )


def _parse_docx(path: Path) -> CanonicalDocument:
    with zipfile.ZipFile(path) as archive:
        total_uncompressed = 0
        member_names: set[str] = set()
        for info in archive.infolist():
            normalized_name = info.filename.replace("\\", "/")
            member_path = PurePosixPath(normalized_name)
            is_windows_absolute = (
                len(normalized_name) >= 3
                and normalized_name[1] == ":"
                and normalized_name[2] == "/"
            )
            if (
                "\x00" in normalized_name
                or member_path.is_absolute()
                or is_windows_absolute
                or ".." in member_path.parts
            ):
                raise ValueError("DOCX archive contains an unsafe member path")
            if normalized_name in member_names:
                raise ValueError("DOCX archive contains duplicate member names")
            member_names.add(normalized_name)
            file_mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(file_mode):
                raise ValueError("symbolic links in DOCX archives are not supported")
            if info.flag_bits & 0x1:
                raise ValueError("encrypted DOCX archives are not supported")
            total_uncompressed += info.file_size
            if total_uncompressed > _MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ValueError("DOCX archive exceeds the uncompressed size limit")
        root = _parse_docx_xml(archive.read("word/document.xml"))
        title = ""
        try:
            core = _parse_docx_xml(archive.read("docProps/core.xml"))
            title_node = core.find("{http://purl.org/dc/elements/1.1/}title")
            title = (title_node.text or "").strip() if title_node is not None else ""
        except KeyError:
            pass
    sections: list[Section] = []
    body = root.find(f"{_DOCX_NS}body")
    if body is None:
        return _document(path, "docx", sections)
    paragraph_number = 0
    table_number = 0
    heading_path: list[str] = []
    for child in body:
        if child.tag == f"{_DOCX_NS}p":
            paragraph_number += 1
            text = _docx_paragraph_text(child)
            if text:
                style = child.find(f"{_DOCX_NS}pPr/{_DOCX_NS}pStyle")
                style_name = style.get(f"{_DOCX_NS}val", "") if style is not None else ""
                level = (
                    int(style_name.removeprefix("Heading"))
                    if style_name.startswith("Heading")
                    and style_name.removeprefix("Heading").isdigit()
                    else None
                )
                sections.append(
                    Section(
                        text=text,
                        location={"paragraph": paragraph_number},
                        heading_path=list(heading_path),
                    )
                )
                if level is not None and 1 <= level <= 6:
                    heading_path = heading_path[: level - 1] + [text]
        elif child.tag == f"{_DOCX_NS}tbl":
            table_number += 1
            for row_number, row in enumerate(child.iter(f"{_DOCX_NS}tr"), start=1):
                cells = []
                for cell in row.findall(f"{_DOCX_NS}tc"):
                    cells.append(_docx_cell_text(cell))
                text = " | ".join(cells).strip()
                if text:
                    sections.append(
                        Section(
                            text=text,
                            location={"table": table_number, "row": row_number},
                            heading_path=list(heading_path),
                        )
                    )
    return _document(path, "docx", sections, parser_version="docx-v4", title=title)


def _parse_json(path: Path) -> CanonicalDocument:
    value = json.loads(_read_utf8_text(path))
    records = value if isinstance(value, list) else [value]
    sections = [
        Section(
            text=json.dumps(record, ensure_ascii=False, sort_keys=True),
            location={"record": index},
        )
        for index, record in enumerate(records, start=1)
    ]
    return _document(path, "json", sections)


def _parse_yaml(path: Path) -> CanonicalDocument:
    """Parse one YAML document without constructing application objects."""

    value = yaml.safe_load(_read_utf8_text(path))
    if value is None:
        raise ValueError(f"empty parsed document: {path}")
    records = value if isinstance(value, list) else [value]
    sections = [
        Section(
            text=json.dumps(record, ensure_ascii=False, sort_keys=True, default=str),
            location={"record": index},
        )
        for index, record in enumerate(records, start=1)
    ]
    return _document(path, "yaml", sections, parser_version="yaml-v1")


def _parse_rtf(path: Path) -> CanonicalDocument:
    """Extract readable text from basic RTF without interpreting embedded objects."""

    raw = path.read_bytes()
    decoded = raw.decode("cp1252")
    if not decoded.lstrip().startswith("{\\rtf"):
        raise ValueError("RTF header is missing")
    text = _strip_rtf_ignored_groups(decoded)
    text = _RTF_HEX_ESCAPE.sub(
        lambda match: bytes.fromhex(match.group(1)).decode("cp1252"), text
    )
    text = _RTF_UNICODE_ESCAPE.sub(
        lambda match: chr(int(match.group(1)) % 65536), text
    )
    text = text.replace(r"\\", "\\").replace(r"\{", "{").replace(r"\}", "}")
    text = text.replace(r"\par", "\n").replace(r"\line", "\n").replace(r"\tab", "\t")
    text = _RTF_CONTROL_WORD.sub("", text)
    text = text.replace("{", "").replace("}", "")
    sections = [
        Section(text=part.strip(), location={"format": "rtf", "index": index})
        for index, part in enumerate(text.splitlines(), start=1)
        if part.strip()
    ]
    return _document(path, "rtf", sections, parser_version="rtf-v1")


def _strip_rtf_ignored_groups(text: str) -> str:
    """Remove nested metadata/object groups before control-word normalization."""

    output: list[str] = []
    ignored_stack = [False]
    index = 0
    while index < len(text):
        character = text[index]
        if character == "{":
            destination = re.match(r"\s*\\\*?([a-zA-Z]+)", text[index + 1 :])
            ignored = ignored_stack[-1] or (
                destination is not None
                and destination.group(1).casefold() in _RTF_IGNORED_DESTINATIONS
            )
            ignored_stack.append(ignored)
            if not ignored:
                output.append(character)
        elif character == "}":
            if len(ignored_stack) == 1:
                raise ValueError("RTF group closing brace is unbalanced")
            ignored_stack.pop()
            if not ignored_stack[-1]:
                output.append(character)
        elif not ignored_stack[-1]:
            output.append(character)
        index += 1
    if len(ignored_stack) != 1:
        raise ValueError("RTF group opening brace is unbalanced")
    return "".join(output)


def _parse_jsonl(path: Path) -> CanonicalDocument:
    sections: list[Section] = []
    for line_number, line in enumerate(_read_utf8_text(path).splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        sections.append(
            Section(
                text=json.dumps(record, ensure_ascii=False, sort_keys=True),
                location={"line": line_number},
            )
        )
    return _document(path, "jsonl", sections, parser_version="jsonl-v1")


def _parse_csv(path: Path) -> CanonicalDocument:
    rows = list(csv.DictReader(io.StringIO(_read_utf8_text(path), newline="")))
    sections = [
        Section(
            text="\n".join(f"{key}: {value}" for key, value in row.items() if value is not None),
            location={"row": index},
        )
        for index, row in enumerate(rows, start=1)
    ]
    return _document(path, "csv", sections)


def _parse_xml(path: Path) -> CanonicalDocument:
    """Extract leaf-node text from local XML exports without following entities."""

    raw_text = _read_utf8_text(path)
    lowered = raw_text.casefold()
    if any(marker in lowered for marker in _XML_FORBIDDEN_DECLARATIONS):
        raise ValueError("XML DTD/entity declarations are not supported")
    root = ElementTree.fromstring(raw_text)
    sections: list[Section] = []

    def local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    def visit(element: ElementTree.Element, path_parts: list[str]) -> None:
        current_path = [*path_parts, local_name(element.tag)]
        children = list(element)
        if not children:
            text = " ".join(part.strip() for part in element.itertext() if part.strip())
            if text:
                sections.append(
                    Section(
                        text=text,
                        location={"format": "xml", "path": "/" + "/".join(current_path)},
                    )
                )
            return
        for child in children:
            visit(child, current_path)

    visit(root, [])
    return _document(path, "xml", sections, parser_version="xml-v1")


def _parse_eml(path: Path) -> CanonicalDocument:
    """Extract plain-text email bodies while ignoring HTML and attachments."""

    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    parts = message.walk() if message.is_multipart() else (message,)
    bodies = [
        part.get_content()
        for part in parts
        if part.get_content_type() == "text/plain"
        and part.get_content_disposition() != "attachment"
        and part.get_filename() is None
    ]
    body = "\n\n".join(str(value).strip() for value in bodies if str(value).strip())
    sections: list[Section] = []
    buffer: list[str] = []
    start_line = 1

    def flush(end_line: int) -> None:
        if buffer:
            sections.append(
                Section(
                    text="\n".join(buffer).strip(),
                    location={
                        "part": len(sections) + 1,
                        "start_line": start_line,
                        "end_line": end_line,
                    },
                )
            )
            buffer.clear()

    for line_number, line in enumerate(body.splitlines(), start=1):
        if line.strip():
            if not buffer:
                start_line = line_number
            buffer.append(line.rstrip())
        else:
            flush(line_number - 1)
    flush(len(body.splitlines()))
    return _document(
        path,
        "email",
        sections,
        parser_version="email-v1",
        title=str(message.get("subject") or "").strip(),
    )


def _parse_pdf(path: Path) -> CanonicalDocument:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if getattr(reader, "is_encrypted", False):
        raise ValueError("encrypted PDF files are not supported")
    sections = []
    extracted_chars = 0
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            extracted_chars += len(text)
            if extracted_chars > _MAX_PDF_EXTRACTED_CHARS:
                raise ValueError("PDF extracted text exceeds the size limit")
            sections.append(Section(text=text, location={"page": page_number}))
    if not sections:
        raise ValueError(
            "PDF contains no extractable text; scanned or image-only PDFs may require OCR"
        )
    metadata = getattr(reader, "metadata", None)
    title = str(getattr(metadata, "title", "") or "").strip() if metadata else ""
    return _document(path, "pdf", sections, parser_version="pdf-v2", title=title)


def parse_source_file(
    path: Path, *, max_bytes: int = 10_000_000
) -> CanonicalDocument:
    """Dispatch by suffix while preserving the existing text parser contract."""

    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    if not path.is_file():
        raise ValueError("source path is not a file")
    if path.stat().st_size > max_bytes:
        raise ValueError("source file exceeds the configured size limit")
    suffix = path.suffix.lower()
    if suffix in _SUPPORTED_TEXT:
        return parse_text_file(path, max_bytes=max_bytes)
    if suffix in {".html", ".htm"}:
        return _parse_html(path)
    if suffix == ".docx":
        return _parse_docx(path)
    if suffix == ".json":
        return _parse_json(path)
    if suffix in {".yaml", ".yml"}:
        return _parse_yaml(path)
    if suffix == ".rtf":
        return _parse_rtf(path)
    if suffix in {".jsonl", ".ndjson"}:
        return _parse_jsonl(path)
    if suffix == ".csv":
        return _parse_csv(path)
    if suffix == ".xml":
        return _parse_xml(path)
    if suffix == ".eml":
        return _parse_eml(path)
    if suffix == ".pdf":
        return _parse_pdf(path)
    raise ValueError(f"unsupported source format: {suffix or '<none>'}")
