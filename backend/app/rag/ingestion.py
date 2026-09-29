"""Quebra do documento em trechos e gravação dos embeddings.

Quem sabe ler cada formato é `extraction`; aqui o documento já chegou como uma lista de divisões.
"""

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import Area, Chunk, Document
from app.rag.extraction import IngestionError, Unit, extract
from app.rag.providers import get_embeddings

EMBED_BATCH = 64


@dataclass(frozen=True)
class UnitChunk:
    """Um trecho e o endereço dele: o ordinal que ordena e o rótulo que a pessoa lê."""

    unit: int
    location: str
    index: int
    content: str


def split_units(units: list[Unit], chunk_size: int, chunk_overlap: int) -> list[UnitChunk]:
    """Cada trecho pertence a uma única divisão, então a citação aponta o lugar exato."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: list[UnitChunk] = []
    for unit in units:
        if not unit.text:
            continue
        for piece in splitter.split_text(unit.text):
            chunks.append(
                UnitChunk(unit=unit.ordinal, location=unit.location, index=len(chunks), content=piece)
            )
    return chunks


def ingest_document(
    session: Session,
    filename: str,
    data: bytes,
    *,
    is_global: bool = True,
    areas: list[Area] | None = None,
) -> Document:
    settings = get_settings()
    kind, units = extract(filename, data)
    pieces = split_units(units, settings.chunk_size, settings.chunk_overlap)
    if not pieces:
        raise IngestionError(_no_text_message(kind))

    embeddings = get_embeddings()
    vectors: list[list[float]] = []
    for start in range(0, len(pieces), EMBED_BATCH):
        batch = pieces[start : start + EMBED_BATCH]
        vectors.extend(embeddings.embed_documents([p.content for p in batch]))

    document = Document(
        filename=filename,
        kind=kind,
        num_units=len(units),
        size_bytes=len(data),
        file=data,
        is_global=is_global,
        areas=list(areas or []),
    )
    document.chunks = [
        Chunk(unit=p.unit, location=p.location, chunk_index=p.index, content=p.content, embedding=v)
        for p, v in zip(pieces, vectors, strict=True)
    ]
    session.add(document)
    session.commit()
    return document


def _no_text_message(kind: str) -> str:
    if kind == "pdf":
        return "O PDF não tem texto extraível. Provavelmente é uma imagem escaneada e precisa de OCR."
    return "O arquivo não tem texto que possa ser indexado."
