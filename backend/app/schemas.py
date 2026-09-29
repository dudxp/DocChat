from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.config import SearchMode


class HealthOut(BaseModel):
    status: str
    provider: str
    chat_model: str
    embedding_model: str
    search_mode: SearchMode
    top_k: int


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    num_pages: int
    size_bytes: int
    chunk_count: int
    created_at: datetime


class UploadError(BaseModel):
    filename: str
    error: str


class UploadOut(BaseModel):
    documents: list[DocumentOut]
    errors: list[UploadError]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = []
    document_ids: list[int] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    search_mode: SearchMode | None = None


class SourceOut(BaseModel):
    number: int
    document_id: int
    filename: str
    page: int
    content: str
    similarity: float
    cited: bool


class ChatOut(BaseModel):
    answer: str
    search_query: str
    sources: list[SourceOut]
    latency_ms: int


class EvalCaseIn(BaseModel):
    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    document_id: int | None = None
    expected_page: int | None = Field(default=None, ge=1)


class EvalCaseOut(EvalCaseIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_filename: str | None = None


class EvalCaseImport(BaseModel):
    """Formato do arquivo de gabarito: o documento é indicado pelo nome do arquivo."""

    question: str
    expected_answer: str
    document: str | None = None
    expected_page: int | None = None


class ImportOut(BaseModel):
    imported: int
    skipped: list[str]


class EvalRunIn(BaseModel):
    top_k: int | None = Field(default=None, ge=1, le=20)
    search_mode: SearchMode | None = None
    use_judge: bool = True
    case_ids: list[int] | None = None


class EvalResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int | None
    question: str
    expected_answer: str
    expected_page: int | None
    answer: str
    retrieved: list[dict]
    retrieval_hit: bool | None
    reciprocal_rank: float | None
    citation_hit: bool | None
    answer_f1: float
    judge_score: float | None
    judge_reason: str | None
    latency_ms: int


class EvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    config: dict
    summary: dict


class EvalRunDetailOut(EvalRunOut):
    results: list[EvalResultOut]
