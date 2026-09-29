"""Leitura do PDF, quebra em trechos e gravação dos embeddings."""

import io
import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chunk, Document
from app.providers import get_embeddings

EMBED_BATCH = 64


class IngestionError(ValueError):
    pass


@dataclass(frozen=True)
class PageChunk:
    page: int
    index: int
    content: str


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"-\n(\w)", r"\1", text)  # palavra hifenizada na quebra de linha
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pages(data: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(data))
        return [clean_text(page.extract_text() or "") for page in reader.pages]
    except (PdfReadError, ValueError, KeyError) as exc:
        raise IngestionError("Não foi possível ler o PDF. O arquivo pode estar corrompido.") from exc


def split_pages(pages: list[str], chunk_size: int, chunk_overlap: int) -> list[PageChunk]:
    """Cada trecho pertence a uma única página, então a citação aponta a página exata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: list[PageChunk] = []
    for page_number, text in enumerate(pages, start=1):
        if not text:
            continue
        for piece in splitter.split_text(text):
            chunks.append(PageChunk(page=page_number, index=len(chunks), content=piece))
    return chunks


def ingest_pdf(session: Session, filename: str, data: bytes) -> Document:
    settings = get_settings()
    pages = extract_pages(data)
    pieces = split_pages(pages, settings.chunk_size, settings.chunk_overlap)
    if not pieces:
        raise IngestionError("O PDF não tem texto extraível. Provavelmente é uma imagem escaneada e precisa de OCR.")

    embeddings = get_embeddings()
    vectors: list[list[float]] = []
    for start in range(0, len(pieces), EMBED_BATCH):
        batch = pieces[start : start + EMBED_BATCH]
        vectors.extend(embeddings.embed_documents([p.content for p in batch]))

    document = Document(filename=filename, num_pages=len(pages), size_bytes=len(data), file=data)
    document.chunks = [
        Chunk(page=p.page, chunk_index=p.index, content=p.content, embedding=v)
        for p, v in zip(pieces, vectors, strict=True)
    ]
    session.add(document)
    session.commit()
    return document
