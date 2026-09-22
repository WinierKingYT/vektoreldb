"""Generate review-required query candidates from the current local corpus.

This tool deliberately produces candidate cases, not final relevance judgments.
The output stays local and must be reviewed before a fixture manifest can become
ready.
"""

from __future__ import annotations

import argparse
import json
import re
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


def _phrase(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text.replace("#", " ").replace("`", " ")).strip()
    words = cleaned.split()
    return " ".join(words[:limit]) or "belge içeriği"


def _ascii_typo(text: str) -> str:
    replacements = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    converted = text.translate(replacements)
    return converted[:-1] if len(converted) > 12 else converted


def _candidate_text(query_type: str, text: str, heading: str) -> str:
    short = _phrase(text, 7)
    if query_type == "semantic":
        return f"{short} ne anlatıyor"
    if query_type == "exact_identifier":
        return f"{_phrase(heading or text, 5)} başlığı"
    if query_type == "typo":
        return _ascii_typo(short)
    if query_type == "morphology":
        return f"{short} hakkında bilgi"
    if query_type == "long_context":
        return f"{_phrase(text, 11)} ile ilgili ayrıntılı açıklama ve bağlam"
    return f"Bu corpus dışında kalan {short} konusu var mı"


def build_candidates(
    root: Path, corpus_manifest: Path, *, count: int = 300
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
            chunks_by_source[relative_path].append(
                (chunk.chunk_id, chunk.text, "/".join(chunk.heading_path), bucket)
            )

    selected: list[tuple[str, str, str, str]] = []
    source_names = sorted(chunks_by_source)
    depth = 0
    while len(selected) < count // len(_QUERY_TYPES):
        added = False
        for source_name in source_names:
            source_chunks = chunks_by_source[source_name]
            if depth < len(source_chunks) and len(selected) < count // len(_QUERY_TYPES):
                selected.append(source_chunks[depth])
                added = True
        if not added:
            break
        depth += 1
    if len(selected) != count // len(_QUERY_TYPES):
        raise ValueError("corpus does not contain enough parsed chunks")

    cases: list[dict[str, object]] = []
    seen_texts: set[str] = set()
    for index, (chunk_id, text, heading, bucket) in enumerate(selected):
        split = _SPLITS[0 if index < 30 else 1 if index < 40 else 2]
        for type_index, query_type in enumerate(_QUERY_TYPES):
            query_number = index * len(_QUERY_TYPES) + type_index + 1
            candidate_text = _candidate_text(query_type, text, heading)
            if candidate_text in seen_texts:
                suffix = _phrase(heading, 3) if heading else f"bölüm {index + 1}"
                candidate_text = f"{candidate_text} {suffix}"
            if candidate_text in seen_texts:
                candidate_text = f"{candidate_text} aday {query_number}"
            seen_texts.add(candidate_text)
            cases.append(
                {
                    "query_id": f"personal-v2-q{query_number:03d}",
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


def write_outputs(root: Path, corpus_manifest: Path, fixture: Path, manifest_path: Path) -> None:
    cases = build_candidates(root, corpus_manifest)
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
        "notes": "Corpus-derived candidate fixture; every label requires single-owner review.",
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
    args = parser.parse_args()
    write_outputs(args.root, args.corpus_manifest, args.fixture, args.manifest)
    print(f"candidate_fixture={args.fixture} count=300 status=review-required")


if __name__ == "__main__":
    main()
