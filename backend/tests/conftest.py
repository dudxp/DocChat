import os
from pathlib import Path

import pytest

# Precisa vir antes de qualquer import de `app`: as configurações são lidas na importação.
os.environ["LLM_PROVIDER"] = "fake"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/docchat_test"
)

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
MANUAL = SAMPLES / "manual-esteira-et200.pdf"
POLICY = SAMPLES / "politica-ferias-beneficios.pdf"


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
        conn.execute(text("DROP TABLE IF EXISTS eval_results, eval_runs, eval_cases, chunks, documents CASCADE"))


@pytest.fixture
def client(database):
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.main import app

    with database.begin() as conn:
        conn.execute(text("TRUNCATE eval_results, eval_runs, eval_cases, chunks, documents RESTART IDENTITY CASCADE"))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def uploaded(client):
    """Os dois PDFs de exemplo já enviados. Devolve {nome do arquivo: id}."""
    files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in (MANUAL, POLICY)]
    response = client.post("/api/documents", files=files)
    assert response.status_code == 201, response.text
    return {d["filename"]: d["id"] for d in response.json()["documents"]}
