"""RAG context packaging without generation or instruction execution."""

import re
from dataclasses import dataclass
from html import escape

from personal_vector_db.retrieval import RetrievalResult


@dataclass(frozen=True)
class ContextCitation:
    citation_id: str
    chunk_id: str
    document_id: str
    source_uri: str
    title: str
    location: dict[str, object]
    heading_path: tuple[str, ...]
    score: float
    embedding_manifest_id: str
    retrieval_stage: str
    parser_version: str
    document_status: str
    security_flags: tuple[str, ...]


@dataclass(frozen=True)
class RAGContext:
    text: str
    citations: tuple[ContextCitation, ...]
    truncated: bool
    candidate_count: int = 0
    included_evidence_count: int = 0
    omitted_evidence_count: int = 0
    used_chars: int = 0
    duplicate_candidate_count: int = 0


@dataclass(frozen=True)
class RAGGenerationDecision:
    """Safe handoff decision; it never asserts answer factuality."""

    allowed: bool
    reason: str
    citation_ids: tuple[str, ...]
    context_truncated: bool = False


@dataclass(frozen=True)
class CitationCheck:
    cited_ids: tuple[str, ...]
    invalid_ids: tuple[str, ...]
    citation_precision: float

    @property
    def valid(self) -> bool:
        """Whether the answer contains at least one known, valid marker."""

        return bool(self.cited_ids) and not self.invalid_ids


@dataclass(frozen=True)
class CitationCoverage:
    """Reference coverage only; not a factuality or faithfulness judgment."""

    citation_check: CitationCheck
    cited_chunk_ids: tuple[str, ...]
    missing_chunk_ids: tuple[str, ...]
    coverage: float


# Accept the documented bare/bracketed marker forms without matching a marker
# embedded in an unrelated identifier (for example, ``E1abc``).
_CITATION_PATTERN = re.compile(r"(?<![A-Za-z0-9_])\[?(E\d+)\]?(?![A-Za-z0-9_])")


def assess_rag_generation(
    context: RAGContext, *, abstention_reason: str | None = None
) -> RAGGenerationDecision:
    """Decide whether a downstream generator may receive this context.

    This is a boundary check, not an answer-quality or factuality judgment.
    Empty/threshold-abstained retrieval and evidence marked for review are
    fail-closed; active, cited evidence is eligible for generation.
    """

    citation_ids = tuple(citation.citation_id for citation in context.citations)
    if not citation_ids:
        reason = (
            "retrieval_below_min_score"
            if abstention_reason == "below_min_score"
            else "no_evidence"
        )
        return RAGGenerationDecision(False, reason, (), context.truncated)
    if any(
        citation.document_status != "active" or citation.security_flags
        for citation in context.citations
    ):
        return RAGGenerationDecision(
            False, "evidence_requires_review", citation_ids, context.truncated
        )
    if (
        not context.text.strip()
        or context.included_evidence_count != len(context.citations)
        or context.used_chars != len(context.text)
    ):
        return RAGGenerationDecision(
            False, "invalid_context", citation_ids, context.truncated
        )
    if context.truncated:
        return RAGGenerationDecision(
            False, "context_truncated", citation_ids, context.truncated
        )
    return RAGGenerationDecision(True, "evidence_available", citation_ids, context.truncated)


def build_rag_context(
    results: list[RetrievalResult], *, max_chars: int = 12_000
) -> RAGContext:
    """Package ranked retrieval evidence for a downstream RAG generator.

    Source text is escaped and wrapped as data. The function does not interpret,
    execute, or merge source instructions with system/developer instructions.
    Whole evidence blocks are kept so a citation never points to a partial chunk.
    """

    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    blocks: list[str] = []
    citations: list[ContextCitation] = []
    seen_chunk_ids: set[str] = set()
    used_chars = 0
    truncated = False
    candidate_count = 0
    omitted_evidence_count = 0
    duplicate_candidate_count = 0
    for result in results:
        if result.chunk_id in seen_chunk_ids:
            duplicate_candidate_count += 1
            continue
        seen_chunk_ids.add(result.chunk_id)
        candidate_count += 1
        citation = ContextCitation(
            citation_id=f"E{len(citations) + 1}",
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            source_uri=result.source_uri,
            title=result.title,
            location=result.location,
            heading_path=result.heading_path,
            score=result.score,
            embedding_manifest_id=result.embedding_manifest_id,
            retrieval_stage=result.retrieval_stage,
            parser_version=result.parser_version,
            document_status=result.document_status,
            security_flags=result.security_flags,
        )
        block = (
            f'<evidence id="{citation.citation_id}" '
            f'document_id="{escape(result.document_id)}" '
            f'chunk_id="{escape(result.chunk_id)}" '
            f'title="{escape(result.title)}" '
            f'heading_path="{escape(" > ".join(result.heading_path))}" '
            f'score="{result.score:.6f}">\n'
            f"{escape(result.text)}\n"
            "</evidence>"
        )
        separator = "\n" if blocks else ""
        if used_chars + len(separator) + len(block) > max_chars:
            truncated = True
            omitted_evidence_count += 1
            continue
        blocks.append(separator + block)
        citations.append(citation)
        used_chars += len(separator) + len(block)
    return RAGContext(
        text="".join(blocks),
        citations=tuple(citations),
        truncated=truncated,
        candidate_count=candidate_count,
        included_evidence_count=len(citations),
        omitted_evidence_count=omitted_evidence_count,
        used_chars=used_chars,
        duplicate_candidate_count=duplicate_candidate_count,
    )


def validate_rag_answer_citations(answer: str, context: RAGContext) -> CitationCheck:
    """Check that answer citation markers point to supplied evidence blocks.

    This validates reference integrity only; it does not claim factuality,
    relevance, or faithfulness of the generated answer.
    """

    if not isinstance(answer, str):
        raise ValueError("answer must be a string")
    cited_ids = tuple(dict.fromkeys(_CITATION_PATTERN.findall(answer)))
    known_ids = {citation.citation_id for citation in context.citations}
    invalid_ids = tuple(citation_id for citation_id in cited_ids if citation_id not in known_ids)
    precision = (
        (len(cited_ids) - len(invalid_ids)) / len(cited_ids) if cited_ids else 1.0
    )
    return CitationCheck(
        cited_ids=cited_ids,
        invalid_ids=invalid_ids,
        citation_precision=precision,
    )


def evaluate_rag_citation_coverage(
    answer: str, context: RAGContext, expected_chunk_ids: set[str] | frozenset[str]
) -> CitationCoverage:
    """Measure how much of an expected evidence set the answer cites.

    The result intentionally measures only marker integrity and chunk coverage;
    it does not inspect whether the answer is factually supported by the text.
    """

    if not isinstance(expected_chunk_ids, (set, frozenset)):
        raise ValueError("expected_chunk_ids must be a set")
    if any(
        not isinstance(chunk_id, str) or not chunk_id.strip()
        for chunk_id in expected_chunk_ids
    ):
        raise ValueError("expected_chunk_ids must contain non-empty strings")
    citation_check = validate_rag_answer_citations(answer, context)
    citations_by_id = {citation.citation_id: citation for citation in context.citations}
    cited_chunk_ids = tuple(
        dict.fromkeys(
            citations_by_id[citation_id].chunk_id
            for citation_id in citation_check.cited_ids
            if citation_id in citations_by_id
        )
    )
    cited_set = set(cited_chunk_ids)
    missing_chunk_ids = tuple(sorted(set(expected_chunk_ids) - cited_set))
    coverage = (
        len(set(expected_chunk_ids) - set(missing_chunk_ids)) / len(expected_chunk_ids)
        if expected_chunk_ids
        else 1.0
    )
    return CitationCoverage(
        citation_check=citation_check,
        cited_chunk_ids=cited_chunk_ids,
        missing_chunk_ids=missing_chunk_ids,
        coverage=coverage,
    )
