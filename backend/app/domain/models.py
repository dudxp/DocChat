from datetime import UTC, datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, deferred, mapped_column, relationship

from app.core.config import get_settings

EMBEDDING_DIM = get_settings().vector_dim


class DocumentKind(StrEnum):
    """Formato do arquivo original. Decide como extrair o texto e como o front o exibe."""

    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    TEXT = "text"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


# Um documento pode ser visível para várias áreas, e um usuário pode pertencer a várias áreas.
document_areas = Table(
    "document_areas",
    Base.metadata,
    Column("document_id", ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("area_id", ForeignKey("areas.id", ondelete="CASCADE"), primary_key=True, index=True),
)

user_areas = Table(
    "user_areas",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("area_id", ForeignKey("areas.id", ondelete="CASCADE"), primary_key=True),
)


class Area(Base):
    __tablename__ = "areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    areas: Mapped[list[Area]] = relationship(secondary=user_areas, order_by="Area.name")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    # Em que o documento se divide: página no PDF, planilha no Excel, slide na apresentação.
    kind: Mapped[str] = mapped_column(String(16), default=DocumentKind.PDF, server_default=DocumentKind.PDF)
    num_units: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    # O arquivo original fica no banco para o front abrir no trecho citado.
    file: Mapped[bytes] = deferred(mapped_column(LargeBinary))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Global: todo mundo vê. Caso contrário, só quem pertence a uma das áreas do documento.
    is_global: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    areas: Mapped[list[Area]] = relationship(secondary=document_areas, order_by="Area.name")

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    # Onde o trecho está: `unit` ordena e endereça, `location` é o que a pessoa lê na citação.
    unit: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String(120))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    # Coluna gerada pelo próprio Postgres para a busca textual da busca híbrida.
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('portuguese', content)", persisted=True))

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )


class EvalCase(Base):
    """Uma pergunta do gabarito: o que se espera como resposta e em que trecho ela está."""

    __tablename__ = "eval_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    expected_unit: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[Document | None] = relationship()


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    config: Mapped[dict] = mapped_column(JSON)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)

    results: Mapped[list["EvalResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True, order_by="EvalResult.id"
    )


class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("eval_runs.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("eval_cases.id", ondelete="SET NULL"))
    question: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str] = mapped_column(Text)
    expected_unit: Mapped[int | None] = mapped_column(Integer)
    answer: Mapped[str] = mapped_column(Text)
    retrieved: Mapped[list] = mapped_column(JSON)
    retrieval_hit: Mapped[bool | None] = mapped_column(Boolean)
    reciprocal_rank: Mapped[float | None] = mapped_column(Float)
    citation_hit: Mapped[bool | None] = mapped_column(Boolean)
    answer_f1: Mapped[float] = mapped_column(Float)
    judge_score: Mapped[float | None] = mapped_column(Float)
    judge_reason: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer)

    run: Mapped[EvalRun] = relationship(back_populates="results")
