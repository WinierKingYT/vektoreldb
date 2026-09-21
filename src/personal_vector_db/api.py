"""Thin HTTP retrieval API; generation remains in the external RAG layer."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from personal_vector_db.ingest import IngestService
from personal_vector_db.retrieval import (
    MAX_QUERY_CHARS,
    RetrievalFilter,
    RetrievalResult,
    RetrievalService,
)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    top_k: int = Field(default=8, ge=1, le=50)
    min_score: float | None = Field(default=None, ge=-1, le=1)
    document_ids: list[str] = Field(default_factory=list, max_length=100)
    source_uris: list[str] = Field(default_factory=list, max_length=100)
    source_types: list[str] = Field(default_factory=list, max_length=10)
    titles: list[str] = Field(default_factory=list, max_length=100)
    rerank: bool = False


class SearchHit(BaseModel):
    document_id: str
    chunk_id: str
    text: str
    score: float
    source_uri: str
    title: str
    location: dict[str, object]
    heading_path: list[str] = Field(default_factory=list)
    embedding_manifest_id: str
    retrieval_stage: str
    parser_version: str = "unknown"
    document_status: str = "active"
    security_flags: tuple[str, ...] = ()

    @classmethod
    def from_result(cls, result: RetrievalResult) -> "SearchHit":
        return cls(**result.__dict__)


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]
    abstention_reason: Literal["none", "no_candidates", "below_min_score"] = Field(
        default="none"
    )
    candidate_count: int = Field(default=0, ge=0)
    threshold_rejected_count: int = Field(default=0, ge=0)


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_ref: str = Field(min_length=1, max_length=4096)


class IngestResponse(BaseModel):
    document_id: str
    status: str
    chunk_count: int
    embedding_manifest_id: str


def _error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool = False,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "retryable": retryable,
            "request_id": str(uuid4()),
            "details": details or {},
        },
    )


def create_app(retrieval: RetrievalService, ingest: IngestService | None = None) -> FastAPI:
    if ingest is not None and ingest.source_root is None:
        raise ValueError("HTTP ingest requires a configured source_root")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        close = getattr(retrieval.store, "close", None)
        if close is not None:
            close()

    app = FastAPI(title="Personal Vector Database", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(HTTPException)
    async def http_error_handler(_request: Request, error: HTTPException) -> JSONResponse:
        message = error.detail if isinstance(error.detail, str) else "request failed"
        return _error_response(error.status_code, "request_error", message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, _error: RequestValidationError
    ) -> JSONResponse:
        return _error_response(422, "validation_error", "request validation failed")

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, _error: Exception) -> JSONResponse:
        # Do not expose provider, filesystem or database details to API clients.
        return _error_response(500, "internal_error", "internal server error", retryable=True)

    def get_retrieval() -> RetrievalService:
        return retrieval

    def get_ingest() -> IngestService:
        if ingest is None:
            raise HTTPException(status_code=503, detail="ingest service is unavailable")
        return ingest

    @app.get("/v1/health")
    def health(service: Annotated[RetrievalService, Depends(get_retrieval)]) -> dict[str, str]:
        return {"status": "ok" if service.store.healthcheck() else "unavailable"}

    @app.post("/v1/search", response_model=SearchResponse)
    def search(
        request: SearchRequest,
        service: Annotated[RetrievalService, Depends(get_retrieval)],
    ) -> SearchResponse:
        try:
            results = service.search(
                request.query,
                limit=request.top_k,
                min_score=request.min_score,
                filters=RetrievalFilter(
                    document_ids=tuple(request.document_ids),
                    source_uris=tuple(request.source_uris),
                    source_types=tuple(request.source_types),
                    titles=tuple(request.titles),
                ),
                rerank=request.rerank,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return SearchResponse(
            query=request.query,
            results=[SearchHit.from_result(result) for result in results],
            abstention_reason=getattr(results, "abstention_reason", "none"),
            candidate_count=getattr(results, "candidate_count", len(results)),
            threshold_rejected_count=getattr(results, "threshold_rejected_count", 0),
        )

    @app.post("/v1/documents:ingest", response_model=IngestResponse, status_code=202)
    def ingest_document(
        request: IngestRequest,
        service: Annotated[IngestService, Depends(get_ingest)],
    ) -> IngestResponse:
        try:
            result = service.ingest_file(Path(request.file_ref))
        except (OSError, ValueError) as error:
            raise HTTPException(
                status_code=400, detail="ingest request could not be processed"
            ) from error
        return IngestResponse(
            document_id=result.document_id,
            status="indexed",
            chunk_count=result.chunk_count,
            embedding_manifest_id=result.embedding_manifest_id,
        )

    @app.delete("/v1/documents/{document_id}", status_code=202)
    def delete_document(
        document_id: str,
        service: Annotated[IngestService, Depends(get_ingest)],
    ) -> dict[str, str]:
        try:
            service.delete_document(document_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"document_id": document_id, "status": "deleted"}

    @app.post("/v1/documents/{document_id}:reindex", response_model=IngestResponse, status_code=202)
    def reindex_document(
        document_id: str,
        request: IngestRequest,
        service: Annotated[IngestService, Depends(get_ingest)],
    ) -> IngestResponse:
        try:
            result = service.reindex_file(Path(request.file_ref), document_id)
        except (OSError, ValueError) as error:
            raise HTTPException(
                status_code=400, detail="reindex request could not be processed"
            ) from error
        return IngestResponse(
            document_id=result.document_id,
            status="indexed",
            chunk_count=result.chunk_count,
            embedding_manifest_id=result.embedding_manifest_id,
        )

    return app
