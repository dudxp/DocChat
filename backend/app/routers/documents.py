from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload, undefer

from app.access import Access, visible_documents
from app.auth import AdminUser, CurrentUser, current_user_or_query
from app.config import get_settings
from app.db import SessionDep
from app.ingestion import IngestionError, ingest_pdf
from app.models import Chunk, Document, User
from app.routers.admin import load_areas
from app.schemas import AreaOut, DocumentAccessIn, DocumentOut, UploadError, UploadOut

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _to_out(doc: Document, chunk_count: int) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        num_pages=doc.num_pages,
        size_bytes=doc.size_bytes,
        chunk_count=chunk_count,
        created_at=doc.created_at,
        is_global=doc.is_global,
        areas=[AreaOut.model_validate(a) for a in doc.areas],
    )


def _check_access(is_global: bool, area_ids: list[int]) -> None:
    if not is_global and not area_ids:
        raise HTTPException(422, "Marque o documento como global ou escolha ao menos uma área.")


@router.get("", response_model=list[DocumentOut])
def list_documents(user: CurrentUser, session: SessionDep):
    """Cada usuário só vê os documentos globais e os das suas áreas."""
    counts = select(Chunk.document_id, func.count().label("n")).group_by(Chunk.document_id).subquery()
    rows = session.execute(
        select(Document, func.coalesce(counts.c.n, 0))
        .options(selectinload(Document.areas))
        .outerjoin(counts, counts.c.document_id == Document.id)
        .where(visible_documents(Access.for_user(user)))
        .order_by(Document.created_at.desc())
    ).all()
    return [_to_out(doc, n) for doc, n in rows]


@router.post("", response_model=UploadOut, status_code=201)
def upload_documents(
    files: list[UploadFile],
    _: AdminUser,
    session: SessionDep,
    is_global: Annotated[bool, Form()] = True,
    area_ids: Annotated[list[int], Form()] = [],  # noqa: B006 (o FastAPI copia o padrão por requisição)
):
    _check_access(is_global, area_ids)
    areas = load_areas(session, area_ids)
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
            doc = ingest_pdf(session, name, data, is_global=is_global, areas=areas)
            created.append(_to_out(doc, len(doc.chunks)))
        except IngestionError as exc:
            session.rollback()
            errors.append(UploadError(filename=name, error=str(exc)))

    if not created and errors:
        raise HTTPException(status_code=422, detail=[e.model_dump() for e in errors])
    return UploadOut(documents=created, errors=errors)


@router.put("/{document_id}/access", response_model=DocumentOut)
def update_access(document_id: int, body: DocumentAccessIn, _: AdminUser, session: SessionDep):
    doc = session.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Documento não encontrado.")
    _check_access(body.is_global, body.area_ids)
    doc.is_global = body.is_global
    doc.areas = load_areas(session, body.area_ids)
    session.commit()
    count = session.scalar(select(func.count()).select_from(Chunk).where(Chunk.document_id == doc.id))
    return _to_out(doc, count or 0)


@router.get("/{document_id}/file")
def download_file(document_id: int, user: Annotated[User, Depends(current_user_or_query)], session: SessionDep):
    doc = session.scalar(
        select(Document)
        .options(undefer(Document.file))
        .where(Document.id == document_id, visible_documents(Access.for_user(user)))
    )
    # 404 também quando o documento existe mas não é visível: não revela que ele existe.
    if doc is None:
        raise HTTPException(404, "Documento não encontrado.")
    return Response(
        content=doc.file,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int, _: AdminUser, session: SessionDep):
    doc = session.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Documento não encontrado.")
    session.delete(doc)
    session.commit()
