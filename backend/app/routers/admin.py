"""Cadastro de áreas e usuários, restrito a administradores."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth import AdminUser, CurrentUser
from app.db import SessionDep
from app.models import Area, User
from app.schemas import AreaIn, AreaOut, UserCreate, UserOut, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/api", tags=["admin"])


def load_areas(session: Session, area_ids: list[int]) -> list[Area]:
    areas = list(session.scalars(select(Area).where(Area.id.in_(area_ids)))) if area_ids else []
    if len(areas) != len(set(area_ids)):
        raise HTTPException(422, "Uma das áreas informadas não existe.")
    return areas


def _commit_unique(session: Session, message: str) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, message) from exc


# --- Áreas ---


@router.get("/areas", response_model=list[AreaOut], tags=["areas"])
def list_areas(_: CurrentUser, session: SessionDep):
    return list(session.scalars(select(Area).order_by(Area.name)))


@router.post("/areas", response_model=AreaOut, status_code=201, tags=["areas"])
def create_area(body: AreaIn, _: AdminUser, session: SessionDep):
    area = Area(name=body.name.strip())
    session.add(area)
    _commit_unique(session, "Já existe uma área com esse nome.")
    return area


@router.put("/areas/{area_id}", response_model=AreaOut, tags=["areas"])
def rename_area(area_id: int, body: AreaIn, _: AdminUser, session: SessionDep):
    area = session.get(Area, area_id)
    if area is None:
        raise HTTPException(404, "Área não encontrada.")
    area.name = body.name.strip()
    _commit_unique(session, "Já existe uma área com esse nome.")
    return area


@router.delete("/areas/{area_id}", status_code=204, tags=["areas"])
def delete_area(area_id: int, _: AdminUser, session: SessionDep):
    """Os documentos e usuários só perdem o vínculo com a área; nada mais é apagado."""
    area = session.get(Area, area_id)
    if area is None:
        raise HTTPException(404, "Área não encontrada.")
    session.delete(area)
    session.commit()


# --- Usuários ---


@router.get("/users", response_model=list[UserOut], tags=["users"])
def list_users(_: AdminUser, session: SessionDep):
    return list(session.scalars(select(User).options(selectinload(User.areas)).order_by(User.name)))


@router.post("/users", response_model=UserOut, status_code=201, tags=["users"])
def create_user(body: UserCreate, _: AdminUser, session: SessionDep):
    user = User(
        username=body.username.lower(),
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        is_admin=body.is_admin,
        areas=load_areas(session, body.area_ids),
    )
    session.add(user)
    _commit_unique(session, "Já existe um usuário com esse login.")
    return user


@router.put("/users/{user_id}", response_model=UserOut, tags=["users"])
def update_user(user_id: int, body: UserUpdate, admin: AdminUser, session: SessionDep):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Usuário não encontrado.")
    if user.id == admin.id and not body.is_admin:
        raise HTTPException(422, "Você não pode remover o seu próprio acesso de administrador.")
    user.name = body.name.strip()
    user.is_admin = body.is_admin
    user.areas = load_areas(session, body.area_ids)
    if body.password:
        user.password_hash = hash_password(body.password)
    session.commit()
    return user


@router.delete("/users/{user_id}", status_code=204, tags=["users"])
def delete_user(user_id: int, admin: AdminUser, session: SessionDep):
    if user_id == admin.id:
        raise HTTPException(422, "Você não pode excluir o próprio usuário.")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Usuário não encontrado.")
    session.delete(user)
    session.commit()
