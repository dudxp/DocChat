from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.core.config import SearchMode


class HealthOut(BaseModel):
    status: str
    provider: str
    chat_model: str
    embedding_model: str
    search_mode: SearchMode
    top_k: int


class AreaIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class AreaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str
    is_admin: bool
    areas: list[AreaOut]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    is_admin: bool = False
    area_ids: list[int] = []


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    is_admin: bool = False
    area_ids: list[int] = []
    password: str | None = Field(default=None, min_length=6, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DocumentAccessIn(BaseModel):
    is_global: bool
    area_ids: list[int] = []


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    kind: str
    num_units: int
    size_bytes: int
    chunk_count: int
    created_at: datetime
    is_global: bool
    areas: list[AreaOut]


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
    kind: str
    unit: int
    location: str
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
    expected_unit: int | None = Field(default=None, ge=1)


class EvalCaseOut(EvalCaseIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_filename: str | None = None


class EvalCaseImport(BaseModel):
    """Formato do arquivo de gabarito: o documento é indicado pelo nome do arquivo.

    `expected_page` é o nome antigo de `expected_unit` e continua sendo aceito, para que
    gabaritos exportados antes da mudança ainda possam ser importados.
    """

    model_config = ConfigDict(populate_by_name=True)

    question: str
    expected_answer: str
    document: str | None = None
    expected_unit: int | None = Field(default=None, validation_alias=AliasChoices("expected_unit", "expected_page"))


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
    expected_unit: int | None
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
