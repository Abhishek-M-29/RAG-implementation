from typing import Literal

from pydantic import BaseModel


class SourceChunk(BaseModel):
    text: str
    source: str
    page: int | None = None


class QueryRequest(BaseModel):
    query: str
    session_id: str
    top_k: int | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    cached: bool


class DocumentUploadResponse(BaseModel):
    job_id: str
    status: Literal["queued", "done"]


class DocumentListItem(BaseModel):
    id: str
    filename: str
    chunk_count: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    error: str | None = None


class HealthResponse(BaseModel):
    status: str


class ComponentHealthResponse(BaseModel):
    status: Literal["ok", "not_ready"]
    detail: str | None = None


class ReadyResponse(BaseModel):
    status: Literal["ok", "not_ready"]
    detail: str | None = None
    vector_store: ComponentHealthResponse | None = None
    llm: ComponentHealthResponse | None = None


class DeleteResponse(BaseModel):
    status: str
    id: str


class ConfigResponse(BaseModel):
    vector_store: str
    llm_provider: str
    auth_enabled: bool
