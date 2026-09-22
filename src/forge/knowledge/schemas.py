from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class DocumentUpload(Schema):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    filename: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1, max_length=4_000_000)


class DocumentRead(Schema):
    id: UUID
    organization_id: UUID
    title: str
    filename: str
    format: str
    sha256: str
    character_count: int
    chunk_count: int
    page_count: int
    created_at: datetime


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class SearchPreview(SearchInput):
    model_config = ConfigDict(extra="forbid", strict=False)
    document_ids: list[UUID] = Field(min_length=1, max_length=20)


class SearchMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document_id: str
    title: str
    chunk: int
    page: int | None
    excerpt: str


class SearchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    matches: list[SearchMatch]
    note: str
