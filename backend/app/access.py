"""Quem pode ver o quê.

A regra fica aqui, num lugar só, e é aplicada dentro das consultas SQL: um trecho que o usuário
não pode ver nunca chega ao modelo de linguagem, então não há prompt capaz de fazê-lo vazar.
"""

from dataclasses import dataclass

from sqlalchemy import ColumnElement, or_, select, true

from app.models import Document, User, document_areas


@dataclass(frozen=True)
class Access:
    """area_ids=None significa acesso irrestrito (administrador)."""

    area_ids: tuple[int, ...] | None

    @classmethod
    def for_user(cls, user: User) -> "Access":
        return cls(None if user.is_admin else tuple(a.id for a in user.areas))

    @classmethod
    def unrestricted(cls) -> "Access":
        return cls(None)


def visible_documents(access: Access) -> ColumnElement[bool]:
    """Condição sobre Document: global, ou compartilhado com alguma área do usuário."""
    if access.area_ids is None:
        return true()
    shared = select(document_areas.c.document_id).where(document_areas.c.area_id.in_(access.area_ids))
    return or_(Document.is_global, Document.id.in_(shared))


def visible_document_ids(access: Access):
    return select(Document.id).where(visible_documents(access))
