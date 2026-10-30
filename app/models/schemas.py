from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
from enum import Enum


# ── Auth ────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Min 8 chars")
    full_name: Optional[str] = Field(None, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Documents ────────────────────────────────────────────────────────────────

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentOut(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_size: Optional[int]
    file_type: str
    page_count: Optional[int]
    chunk_count: Optional[int]
    status: DocumentStatus
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    documents: List[DocumentOut]
    total: int


class DocumentDetail(DocumentOut):
    download_url: Optional[str] = None


# ── RAG / Query ──────────────────────────────────────────────────────────────

class Source(BaseModel):
    document_id: str
    filename: str
    page: Optional[int] = None
    text_snippet: str


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    document_ids: Optional[List[str]] = None   # None = search all user docs


class QueryResponse(BaseModel):
    answer: str
    sources: List[Source] = []
    confidence: Optional[float] = None


# ── Health ──────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str = "1.0.0"