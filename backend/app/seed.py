"""Carrega os PDFs de exemplo e o gabarito, para ter algo para perguntar logo na primeira execução.

python -m app.seed
"""

import json
import os
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.ingestion import ingest_pdf
from app.models import Document, EvalCase

SAMPLES = Path(os.environ.get("SAMPLES_DIR", Path(__file__).resolve().parents[2] / "samples"))


def seed(samples_dir: Path = SAMPLES) -> None:
    init_db()
    with SessionLocal() as session:
        existing = {d.filename: d.id for d in session.scalars(select(Document))}
        for pdf in sorted(samples_dir.glob("*.pdf")):
            if pdf.name in existing:
                print(f"= {pdf.name} já existe")
                continue
            doc = ingest_pdf(session, pdf.name, pdf.read_bytes())
            existing[pdf.name] = doc.id
            print(f"+ {pdf.name}: {doc.num_pages} páginas, {len(doc.chunks)} trechos")

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
