"""Generate review-required query candidates from the current local corpus.

This tool deliberately produces candidate cases, not final relevance judgments.
The output stays local and must be reviewed before a fixture manifest can become
ready.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from personal_vector_db.chunking import chunk_document
from personal_vector_db.corpus import inventory_sources, read_corpus_manifest
from personal_vector_db.parsers import parse_source

_QUERY_TYPES = (
    "semantic",
    "exact_identifier",
    "typo",
    "morphology",
    "long_context",
    "negative",
)
_SPLITS = ("development", "validation", "test")
_SELECTIVITY = ("low", "medium", "high")
_MOJIBAKE_MARKERS = ("Ã", "Ä", "Å", "Â", "â€", "�")
_NEGATIVE_SUBJECTS = (
    "Europa uydusundaki buz tabakası",
    "Amazon havzasındaki pembe nehir yunusları",
    "Antarktika buz çekirdeklerindeki volkanik kül",
    "Göbeklitepe taşlarındaki hayvan kabartmaları",
    "Japon raku seramiğindeki sır çatlakları",
    "Barok keman yapımındaki reçine verniği",
    "Mercan resiflerindeki gece yumurtlaması",
    "Kepler 452b dışgezegeninin atmosferi",
    "Hidrotermal bacalardaki dev tüp solucanları",
    "İnka düğüm kayıt sistemi quipu",
)
_NEGATIVE_ASPECTS = (
    "ölçüm yöntemi",
    "tarihsel değişim",
    "temel bilimsel açıklama",
    "saha araştırması bulguları",
    "güncel sınıflandırma yaklaşımı",
)


def _normalize_for_scan(text: str) -> str:
    translated = text.translate(str.maketrans({"ı": "i", "İ": "I"}))
    decomposed = unicodedata.normalize("NFKD", translated)
    ascii_like = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^\w]+", " ", ascii_like.casefold()).strip()


def _looks_mojibake(text: str) -> bool:
    return any(marker in text for marker in _MOJIBAKE_MARKERS)


def _negative_text(index: int) -> str:
    subject = _NEGATIVE_SUBJECTS[index % len(_NEGATIVE_SUBJECTS)]
    aspect = _NEGATIVE_ASPECTS[index // len(_NEGATIVE_SUBJECTS)]
    return f"Bu corpus'ta {subject} için {aspect} var mı"


def _validate_negative_bank(texts: list[str]) -> None:
    corpus_text = _normalize_for_scan(" ".join(texts))
    for index in range(len(_NEGATIVE_SUBJECTS) * len(_NEGATIVE_ASPECTS)):
        candidate = _normalize_for_scan(_negative_text(index))
        if candidate and candidate in corpus_text:
            raise ValueError("negative intent bank overlaps the current corpus")


def _phrase(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text.replace("#", " ").replace("`", " ")).strip()
    words = cleaned.split()
    return " ".join(words[:limit]) or "belge içeriği"


def _ascii_typo(text: str) -> str:
    replacements = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    converted = text.translate(replacements)
    return converted[:-1] if len(converted) > 12 else converted


def _candidate_text(
    query_type: str, text: str, heading: str, source_name: str, index: int
) -> str:
    short = _phrase(text, 7)
    if query_type == "semantic":
        return f"{short} ne anlatıyor"
    if query_type == "exact_identifier":
        identifier = _phrase(heading or text, 5)
        source_hint = Path(source_name).stem.replace("_", " ").replace("-", " ")
        return f"{identifier} ({source_hint}) başlığı"
    if query_type == "typo":
        return _ascii_typo(short)
    if query_type == "morphology":
        return f"{short} hakkında bilgi"
    if query_type == "long_context":
        return f"{_phrase(text, 11)} ile ilgili ayrıntılı açıklama ve bağlam"
    return _negative_text(index)


def _usable_chunk(text: str, heading: str) -> bool:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) < 40 or len(normalized.split()) < 7:
        return False
    lowered = normalized.casefold()
    scan_text = _normalize_for_scan(normalized)
    if "içindekiler" in lowered or "icindekiler" in scan_text:
        return False
    if "table of contents" in lowered or "table of contents" in scan_text:
        return False
    if "|" in normalized or any(line.count(",") >= 3 for line in normalized.splitlines()):
        return False
    if _looks_mojibake(normalized):
        return False
    if heading.casefold().startswith(("içindekiler", "table of contents")):
        return False
    return True


def build_candidates(
    root: Path, corpus_manifest: Path, *, count: int = 300, version: str = "v3"
) -> list[dict[str, object]]:
    if count < 6 or count % len(_QUERY_TYPES) != 0:
        raise ValueError("count must be a positive multiple of six")
    records = inventory_sources(root)
    read_corpus_manifest(corpus_manifest)
    chunks_by_source: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
    for record in records:
        if record.get("status") != "parsed":
            continue
        relative_path = str(record["relative_path"])
        document = parse_source(root / relative_path)
        chunks = chunk_document(document)
        bucket = str(record["size_bucket"])
        for chunk in chunks:
            heading = "/".join(chunk.heading_path)
            if not _usable_chunk(chunk.text, heading):
                continue
            chunks_by_source[relative_path].append(
                (chunk.chunk_id, chunk.text, heading, bucket)
            )

    selected: list[tuple[str, str, str, str, str]] = []
    source_names = sorted(chunks_by_source)
    depth = 0
    while len(selected) < count // len(_QUERY_TYPES):
        added = False
        for source_name in source_names:
            source_chunks = chunks_by_source[source_name]
            if depth < len(source_chunks) and len(selected) < count // len(_QUERY_TYPES):
                selected.append((source_name, *source_chunks[depth]))
                added = True
        if not added:
            break
        depth += 1
    if len(selected) != count // len(_QUERY_TYPES):
        raise ValueError("corpus does not contain enough parsed chunks")
    corpus_texts = [
        text for chunks in chunks_by_source.values() for _, text, _, _ in chunks
    ]
    _validate_negative_bank(corpus_texts)

    cases: list[dict[str, object]] = []
    seen_texts: set[str] = set()
    for index, (source_name, chunk_id, text, heading, bucket) in enumerate(selected):
        split = _SPLITS[0 if index < 30 else 1 if index < 40 else 2]
        for type_index, query_type in enumerate(_QUERY_TYPES):
            query_number = index * len(_QUERY_TYPES) + type_index + 1
            candidate_text = _candidate_text(query_type, text, heading, source_name, index)
            if candidate_text in seen_texts:
                if query_type == "negative":
                    candidate_text = f"{candidate_text} negative test {query_number}"
                else:
                    suffix = _phrase(heading, 3) if heading else f"bölüm {index + 1}"
                    candidate_text = f"{candidate_text} {suffix} {index + 1}"
            if candidate_text in seen_texts:
                candidate_text = f"{candidate_text} aday {query_number}"
            seen_texts.add(candidate_text)
            cases.append(
                {
                    "query_id": f"personal-{version}-q{query_number:03d}",
                    "text": candidate_text,
                    "relevant_chunk_ids": [] if query_type == "negative" else [chunk_id],
                    "query_type": query_type,
                    "split": split,
                    "size_bucket": bucket,
                    "filter_selectivity": _SELECTIVITY[index % len(_SELECTIVITY)],
                }
            )
    if len(cases) != count:
        raise ValueError("candidate generation produced an unexpected count")
    return cases


def write_outputs(
    root: Path, corpus_manifest: Path, fixture: Path, manifest_path: Path, version: str
) -> None:
    cases = build_candidates(root, corpus_manifest, version=version)
    corpus = read_corpus_manifest(corpus_manifest)
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fixture_manifest = {
        "schema_version": "query-fixture-manifest-v1",
        "status": "contract-only",
        "minimum_query_count": 300,
        "recommended_split": {"development": 0.6, "validation": 0.2, "test": 0.2},
        "split_tolerance": 0.05,
        "required_query_types": list(_QUERY_TYPES),
        "minimum_queries_per_type": 30,
        "required_document_size_buckets": ["small", "medium", "large"],
        "required_filter_selectivity_buckets": list(_SELECTIVITY),
        "corpus_checksum": corpus["corpus_checksum"],
        "parser_version": "mixed",
        "parser_versions": corpus["parser_versions"],
        "chunking_version": corpus["chunking_version"],
        "embedding_manifest_id": None,
        "privacy_classification": "private-local",
        "notes": (
            f"Corpus-derived {version} candidate fixture; every label requires "
            "single-owner review."
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(fixture_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--version", default="v3")
    args = parser.parse_args()
    write_outputs(args.root, args.corpus_manifest, args.fixture, args.manifest, args.version)
    print(
        f"candidate_fixture={args.fixture} count=300 "
        f"version={args.version} status=review-required"
    )


if __name__ == "__main__":
    main()
