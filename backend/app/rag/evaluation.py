"""Avaliação contra o gabarito.

Mede separadamente as duas metades do RAG, porque cada uma falha de um jeito:
- recuperação: o trecho certo apareceu entre os top-k? (hit rate e MRR)
- geração: a resposta cita a página certa e diz o que o gabarito diz? (citação, F1 e nota do juiz)
"""

import json
import re
from collections import Counter
from statistics import mean

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SearchMode, get_settings
from app.domain.models import EvalCase, EvalResult, EvalRun
from app.rag.pipeline import Answer, answer_question
from app.rag.providers import build_chat_model, is_fake, normalize_words

JUDGE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Você avalia respostas de um sistema de perguntas sobre documentos. Compare a resposta "
            "obtida com a resposta de referência e dê uma nota de 0 a 1:\n"
            "1 = mesma informação essencial; 0.5 = parcialmente correta ou incompleta; "
            "0 = errada, contraditória ou disse que não encontrou.\n"
            "Ignore diferenças de redação e as marcações de citação [n]. "
            'Responda só com JSON: {{"score": <número>, "reason": "<uma frase>"}}',
        ),
        (
            "human",
            "Pergunta: {question}\n\nResposta de referência: {expected}\n\nResposta obtida: {answer}",
        ),
    ]
)


def token_f1(prediction: str, reference: str) -> float:
    """F1 de sobreposição de palavras (como no SQuAD), sem acentos e sem citações."""
    pred = normalize_words(re.sub(r"\[\d+\]", "", prediction))
    ref = normalize_words(reference)
    if not pred or not ref:
        return 0.0
    common = sum((Counter(pred) & Counter(ref)).values())
    if common == 0:
        return 0.0
    precision, recall = common / len(pred), common / len(ref)
    return round(2 * precision * recall / (precision + recall), 4)


def _matches(source, case: EvalCase) -> bool:
    if case.document_id is not None and source.document_id != case.document_id:
        return False
    return source.unit == case.expected_unit


def retrieval_metrics(answer: Answer, case: EvalCase) -> tuple[bool | None, float | None]:
    if case.expected_unit is None:
        return None, None
    for position, source in enumerate(answer.sources, start=1):
        if _matches(source, case):
            return True, round(1.0 / position, 4)
    return False, 0.0


def citation_hit(answer: Answer, case: EvalCase) -> bool | None:
    if case.expected_unit is None:
        return None
    return any(_matches(answer.sources[n - 1], case) for n in answer.cited)


def parse_judge(raw: str) -> tuple[float | None, str | None]:
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None, raw.strip()[:500] or None
    try:
        data = json.loads(match.group(0))
        score = max(0.0, min(1.0, float(data.get("score"))))
        return round(score, 2), str(data.get("reason", ""))[:500]
    except (ValueError, TypeError):
        return None, raw.strip()[:500]


def judge(question: str, expected: str, answer: str) -> tuple[float | None, str | None]:
    """LLM como juiz. Com o provedor fake não há juiz, e a nota fica só no F1."""
    if is_fake():
        return None, None
    chain = JUDGE_PROMPT | build_chat_model(get_settings(), temperature=0) | StrOutputParser()
    try:
        return parse_judge(chain.invoke({"question": question, "expected": expected, "answer": answer}))
    except Exception as exc:  # o juiz falhar não deve derrubar a execução inteira
        return None, f"Falha no juiz: {exc}"[:500]


def _avg(values: list) -> float | None:
    values = [float(v) for v in values if v is not None]
    return round(mean(values), 4) if values else None


def summarize(results: list[EvalResult]) -> dict:
    return {
        "cases": len(results),
        "hit_rate": _avg([r.retrieval_hit for r in results]),
        "mrr": _avg([r.reciprocal_rank for r in results]),
        "citation_accuracy": _avg([r.citation_hit for r in results]),
        "answer_f1": _avg([r.answer_f1 for r in results]),
        "judge_score": _avg([r.judge_score for r in results]),
        "avg_latency_ms": int(_avg([r.latency_ms for r in results]) or 0),
    }


def run_evaluation(
    session: Session,
    *,
    top_k: int | None = None,
    mode: SearchMode | None = None,
    use_judge: bool = True,
    case_ids: list[int] | None = None,
) -> EvalRun:
    settings = get_settings()
    top_k = top_k or settings.top_k
    mode = mode or settings.search_mode

    stmt = select(EvalCase).order_by(EvalCase.id)
    if case_ids:
        stmt = stmt.where(EvalCase.id.in_(case_ids))
    cases = list(session.scalars(stmt))
    if not cases:
        raise ValueError("Não há perguntas no gabarito para avaliar.")

    run = EvalRun(
        config={
            "provider": settings.llm_provider,
            "chat_model": settings.chat_model_name,
            "embedding_model": settings.embedding_model_name,
            "top_k": top_k,
            "search_mode": mode,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "judge": use_judge and not is_fake(),
        }
    )

    for case in cases:
        answer = answer_question(session, case.question, top_k=top_k, mode=mode)
        hit, rr = retrieval_metrics(answer, case)
        score, reason = judge(case.question, case.expected_answer, answer.answer) if use_judge else (None, None)
        run.results.append(
            EvalResult(
                case_id=case.id,
                question=case.question,
                expected_answer=case.expected_answer,
                expected_unit=case.expected_unit,
                answer=answer.answer,
                retrieved=[
                    {
                        "document_id": s.document_id,
                        "filename": s.filename,
                        "location": s.location,
                        "similarity": s.similarity,
                    }
                    for s in answer.sources
                ],
                retrieval_hit=hit,
                reciprocal_rank=rr,
                citation_hit=citation_hit(answer, case),
                answer_f1=token_f1(answer.answer, case.expected_answer),
                judge_score=score,
                judge_reason=reason,
                latency_ms=answer.latency_ms,
            )
        )

    run.summary = summarize(run.results)
    session.add(run)
    session.commit()
    return run
