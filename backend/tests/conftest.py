import os
from pathlib import Path

import pytest

# Precisa vir antes de qualquer import de `app`: as configurações são lidas na importação.
os.environ["LLM_PROVIDER"] = "fake"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "senha-admin"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/docchat_test"
)

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
MANUAL = SAMPLES / "manual-esteira-et200.pdf"
POLICY = SAMPLES / "politica-ferias-beneficios.pdf"
SALARIES = SAMPLES / "faixas-salariais-rh.pdf"

TABLES = "eval_results, eval_runs, eval_cases, document_areas, user_areas, chunks, documents, users, areas"


def login(client, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def database():
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from app.db import engine, init_db

    try:
        init_db()
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL com pgvector indisponível: {exc.orig}")
    yield engine
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLES} CASCADE"))


@pytest.fixture
def client(database):
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.main import app

    with database.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    # Ao iniciar, a API cria o administrador do .env. O cliente padrão dos testes já entra como ele.
    with TestClient(app) as c:
        c.headers.update(login(c, "admin", "senha-admin"))
        yield c


@pytest.fixture
def uploaded(client):
    """Os dois PDFs de exemplo já enviados. Devolve {nome do arquivo: id}."""
    files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in (MANUAL, POLICY)]
    response = client.post("/api/documents", files=files)
    assert response.status_code == 201, response.text
    return {d["filename"]: d["id"] for d in response.json()["documents"]}
