"""Carrega os dados de demonstração: áreas, usuários, PDFs de exemplo com o acesso de cada um e o gabarito.

python -m app.seed
"""

import json
import os
from pathlib import Path

from sqlalchemy import select

from app.auth import ensure_admin
from app.db import SessionLocal, init_db
from app.ingestion import ingest_pdf
from app.models import Area, Document, EvalCase, User
from app.security import hash_password

SAMPLES = Path(os.environ.get("SAMPLES_DIR", Path(__file__).resolve().parents[2] / "samples"))

AREAS = ["Engenharia", "Estoque", "Produção", "RH"]

# None = global. Uma lista = visível só para essas áreas.
SAMPLE_ACCESS: dict[str, list[str] | None] = {
    "politica-ferias-beneficios.pdf": None,
    "manual-esteira-et200.pdf": ["Engenharia", "Estoque", "Produção"],
    "faixas-salariais-rh.pdf": ["RH"],
}

DEMO_PASSWORD = "demo1234"
DEMO_USERS = [
    ("engenharia", "Ana (Engenharia)", ["Engenharia"]),
    ("estoque", "Bruno (Estoque)", ["Estoque"]),
    ("rh", "Carla (RH)", ["RH"]),
]


def seed(samples_dir: Path = SAMPLES) -> None:
    init_db()
    ensure_admin()
    with SessionLocal() as session:
        areas = {a.name: a for a in session.scalars(select(Area))}
        for name in AREAS:
            if name not in areas:
                areas[name] = Area(name=name)
                session.add(areas[name])
                print(f"+ área {name}")
        session.flush()

        usernames = set(session.scalars(select(User.username)))
        for username, name, user_areas in DEMO_USERS:
            if username not in usernames:
                session.add(
                    User(
                        username=username,
                        name=name,
                        password_hash=hash_password(DEMO_PASSWORD),
                        areas=[areas[a] for a in user_areas],
                    )
                )
                print(f"+ usuário {username} (senha {DEMO_PASSWORD})")
        session.commit()

        existing = {d.filename: d.id for d in session.scalars(select(Document))}
        for pdf in sorted(samples_dir.glob("*.pdf")):
            if pdf.name in existing:
                print(f"= {pdf.name} já existe")
                continue
            allowed = SAMPLE_ACCESS.get(pdf.name)
            doc = ingest_pdf(
                session,
                pdf.name,
                pdf.read_bytes(),
                is_global=allowed is None,
                areas=[areas[a] for a in allowed or []],
            )
            existing[pdf.name] = doc.id
            scope = "global" if allowed is None else ", ".join(allowed)
            print(f"+ {pdf.name}: {doc.num_pages} páginas, {len(doc.chunks)} trechos ({scope})")

        if session.scalar(select(EvalCase.id).limit(1)) is not None:
            print("= gabarito já carregado")
            return
        cases = json.loads((samples_dir / "gabarito.json").read_text(encoding="utf-8"))
        for item in cases:
            session.add(
                EvalCase(
                    question=item["question"],
                    expected_answer=item["expected_answer"],
                    document_id=existing.get(item.get("document")),
                    expected_page=item.get("expected_page"),
                )
            )
        session.commit()
        print(f"+ gabarito: {len(cases)} perguntas")


if __name__ == "__main__":
    seed()
