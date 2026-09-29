from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.domain.models import EMBEDDING_DIM, Base

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class EmbeddingDimensionMismatch(RuntimeError):
    pass


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    _upgrade_schema()
    _check_embedding_dimension()


def _rename_column(conn, table: str, old: str, new: str) -> None:
    """Postgres não tem RENAME COLUMN IF EXISTS, e o boot precisa poder rodar duas vezes."""
    conn.execute(
        text(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name = '{table}' AND column_name = '{old}')
            THEN ALTER TABLE {table} RENAME COLUMN {old} TO {new};
            END IF;
        END $$;
        """)
    )


def _upgrade_schema() -> None:
    """create_all não altera tabelas que já existem. Bancos criados antes do controle de acesso
    ganham a coluna aqui, e os documentos antigos continuam visíveis para todos."""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_global boolean NOT NULL DEFAULT true"))

        # "Página" só existe no PDF. O endereço de um trecho passou a ser a unidade do documento
        # (página, planilha, slide) mais o rótulo que a pessoa lê na citação.
        _rename_column(conn, "documents", "num_pages", "num_units")
        _rename_column(conn, "chunks", "page", "unit")
        _rename_column(conn, "eval_cases", "expected_page", "expected_unit")
        _rename_column(conn, "eval_results", "expected_page", "expected_unit")
        conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS kind varchar(16) NOT NULL DEFAULT 'pdf'"))
        # Os trechos já existentes são todos de PDF, então o rótulo deles é a página.
        conn.execute(text("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS location varchar(120) NOT NULL DEFAULT ''"))
        conn.execute(text("UPDATE chunks SET location = 'página ' || unit WHERE location = ''"))


def _check_embedding_dimension() -> None:
    """Trocar de provedor muda o tamanho do vetor; avisa em vez de falhar no primeiro insert."""
    with engine.connect() as conn:
        current = conn.execute(
            text("SELECT atttypmod FROM pg_attribute WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'")
        ).scalar()
    if current is not None and current != EMBEDDING_DIM:
        raise EmbeddingDimensionMismatch(
            f"A coluna chunks.embedding tem dimensão {current}, mas o provedor configurado "
            f"gera vetores de {EMBEDDING_DIM}. Recrie o banco (docker compose down -v) ou "
            f"ajuste EMBEDDING_DIM, e envie os documentos de novo."
        )


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
