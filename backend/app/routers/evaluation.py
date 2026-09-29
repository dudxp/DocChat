from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import admin_user
from app.db import SessionDep
from app.evaluation import run_evaluation
from app.models import Document, EvalCase, EvalRun
from app.schemas import (
    EvalCaseImport,
    EvalCaseIn,
    EvalCaseOut,
    EvalRunDetailOut,
    EvalRunIn,
    EvalRunOut,
    ImportOut,
)

# A avaliação roda sobre todos os documentos e é uma ferramenta de quem administra o sistema.
router = APIRouter(prefix="/api/eval", tags=["evaluation"], dependencies=[Depends(admin_user)])


def _case_out(case: EvalCase) -> EvalCaseOut:
    return EvalCaseOut(
        id=case.id,
        question=case.question,
        expected_answer=case.expected_answer,
        document_id=case.document_id,
        expected_page=case.expected_page,
        document_filename=case.document.filename if case.document else None,
    )


def _check_document(session: Session, document_id: int | None) -> None:
    if document_id is not None and session.get(Document, document_id) is None:
        raise HTTPException(422, "Documento informado não existe.")


@router.get("/cases", response_model=list[EvalCaseOut])
def list_cases(session: SessionDep):
    cases = session.scalars(select(EvalCase).options(selectinload(EvalCase.document)).order_by(EvalCase.id))
    return [_case_out(c) for c in cases]


@router.post("/cases", response_model=EvalCaseOut, status_code=201)
def create_case(body: EvalCaseIn, session: SessionDep):
    _check_document(session, body.document_id)
    case = EvalCase(**body.model_dump())
    session.add(case)
    session.commit()
    session.refresh(case)
    return _case_out(case)


@router.put("/cases/{case_id}", response_model=EvalCaseOut)
def update_case(case_id: int, body: EvalCaseIn, session: SessionDep):
    case = session.get(EvalCase, case_id)
    if case is None:
        raise HTTPException(404, "Pergunta não encontrada.")
    _check_document(session, body.document_id)
    for key, value in body.model_dump().items():
        setattr(case, key, value)
    session.commit()
    session.refresh(case)
    return _case_out(case)


@router.delete("/cases/{case_id}", status_code=204)
def delete_case(case_id: int, session: SessionDep):
    case = session.get(EvalCase, case_id)
    if case is None:
        raise HTTPException(404, "Pergunta não encontrada.")
    session.delete(case)
    session.commit()


@router.post("/cases/import", response_model=ImportOut)
def import_cases(items: list[EvalCaseImport], session: SessionDep):
    """Importa um gabarito em JSON, ligando cada pergunta ao documento pelo nome do arquivo."""
    by_name = {d.filename: d.id for d in session.scalars(select(Document))}
    skipped: list[str] = []
    imported = 0
    for item in items:
        document_id = None
        if item.document:
            document_id = by_name.get(item.document)
            if document_id is None:
                skipped.append(f"{item.question} (documento '{item.document}' não enviado)")
                continue
        session.add(
            EvalCase(
                question=item.question,
                expected_answer=item.expected_answer,
                document_id=document_id,
                expected_page=item.expected_page,
            )
        )
        imported += 1
    session.commit()
    return ImportOut(imported=imported, skipped=skipped)


@router.get("/cases/export", response_model=list[EvalCaseImport])
def export_cases(session: SessionDep):
    cases = session.scalars(select(EvalCase).options(selectinload(EvalCase.document)).order_by(EvalCase.id))
    return [
        EvalCaseImport(
            question=c.question,
            expected_answer=c.expected_answer,
            document=c.document.filename if c.document else None,
            expected_page=c.expected_page,
        )
        for c in cases
    ]


@router.post("/runs", response_model=EvalRunDetailOut, status_code=201)
def create_run(body: EvalRunIn, session: SessionDep):
    try:
        run = run_evaluation(
            session,
            top_k=body.top_k,
            mode=body.search_mode,
            use_judge=body.use_judge,
            case_ids=body.case_ids,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return run


@router.get("/runs", response_model=list[EvalRunOut])
def list_runs(session: SessionDep):
    return list(session.scalars(select(EvalRun).order_by(EvalRun.id.desc())))


@router.get("/runs/{run_id}", response_model=EvalRunDetailOut)
def get_run(run_id: int, session: SessionDep):
    run = session.scalar(select(EvalRun).options(selectinload(EvalRun.results)).where(EvalRun.id == run_id))
    if run is None:
        raise HTTPException(404, "Execução não encontrada.")
    return run


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: int, session: SessionDep):
    run = session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(404, "Execução não encontrada.")
    session.delete(run)
    session.commit()
