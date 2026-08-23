from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    id: str | None = None
    score: float | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    chunk_index: int | None = None
    filename: str | None = None
    content: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult] = []


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class QuerySource(BaseModel):
    document_id: str | None = None
    chunk_id: str | None = None
    filename: str | None = None
    chunk_index: int | None = None
    score: float | None = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: list[QuerySource] = []