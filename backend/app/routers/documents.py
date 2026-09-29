from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import undefer

from app.config import get_settings
from app.db import SessionDep
from app.ingestion import IngestionError, ingest_pdf
from app.models import Chunk, Document
from app.schemas import DocumentOut, UploadError, UploadOut

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _to_out(doc: Document, chunk_count: int) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        num_pages=doc.num_pages,
        size_bytes=doc.size_bytes,
        chunk_count=chunk_count,
        created_at=doc.created_at,
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(session: SessionDep):
    counts = select(Chunk.document_id, func.count().label("n")).group_by(Chunk.document_id).subquery()
    rows = session.execute(
        select(Document, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.document_id == Document.id)
        .order_by(Document.created_at.desc())
    ).all()
    return [_to_out(doc, n) for doc, n in rows]


@router.post("", response_model=UploadOut, status_code=201)
def upload_documents(files: list[UploadFile], session: SessionDep):
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    created: list[DocumentOut] = []
    errors: list[UploadError] = []

    for upload in files:
        name = upload.filename or "documento.pdf"
        data = upload.file.read()
        if not name.lower().endswith(".pdf") and upload.content_type != "application/pdf":
            errors.append(UploadError(filename=name, error="Apenas arquivos PDF são aceitos."))
            continue
        if len(data) > max_bytes:
            errors.append(UploadError(filename=name, error=f"Arquivo maior que {get_settings().max_upload_mb} MB."))
            continue
        try:
            doc = ingest_pdf(session, name, data)
            created.append(_to_out(doc, len(doc.chunks)))
        except IngestionError as exc:
            session.rollback()
            errors.append(UploadError(filename=name, error=str(exc)))

    if not created and errors:
        raise HTTPException(status_code=422, detail=[e.model_dump() for e in errors])
    return UploadOut(documents=created, errors=errors)


@router.get("/{document_id}/file")
def download_file(document_id: int, session: SessionDep):
    doc = session.scalar(select(Document).options(undefer(Document.file)).where(Document.id == document_id))
    if doc is None:
        raise HTTPException(404, "Documento não encontrado.")
    return Response(
        content=doc.file,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int, session: SessionDep):
    doc = session.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Documento não encontrado.")
    session.delete(doc)
    session.commit()
