"""Dependências de autenticação para as rotas."""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.access import Access
from app.config import get_settings
from app.db import SessionDep, SessionLocal
from app.models import User
from app.security import decode_token, hash_password

log = logging.getLogger("docchat")

# tokenUrl habilita o botão "Authorize" no Swagger (/docs).
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

UNAUTHORIZED = HTTPException(
    status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada.", headers={"WWW-Authenticate": "Bearer"}
)


def _load_user(session, token: str | None) -> User:
    user_id = decode_token(token) if token else None
    if user_id is None:
        raise UNAUTHORIZED
    user = session.scalar(select(User).options(selectinload(User.areas)).where(User.id == user_id))
    if user is None:
        raise UNAUTHORIZED
    return user


def current_user(session: SessionDep, token: Annotated[str | None, Depends(oauth2)]) -> User:
    return _load_user(session, token)


def current_user_or_query(
    session: SessionDep,
    token: Annotated[str | None, Depends(oauth2)],
    access_token: Annotated[str | None, Query(include_in_schema=False)] = None,
) -> User:
    """Para links abertos direto pelo navegador (o PDF), que não conseguem mandar cabeçalho."""
    return _load_user(session, token or access_token)


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas administradores podem fazer isso.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(admin_user)]


def access_of(user: User) -> Access:
    return Access.for_user(user)


def ensure_admin() -> None:
    """Cria o primeiro administrador a partir do .env quando ainda não existe nenhum usuário."""
    settings = get_settings()
    with SessionLocal() as session:
        if session.scalar(select(User.id).limit(1)) is not None:
            return
        session.add(
            User(
                username=settings.admin_username,
                name="Administrador",
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
            )
        )
        session.commit()
    if settings.admin_password == "admin":
        log.warning("Administrador criado com a senha padrão 'admin'. Defina ADMIN_PASSWORD no .env.")
