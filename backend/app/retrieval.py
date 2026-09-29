"""Busca dos trechos: vetorial (pgvector) ou híbrida (vetorial + texto completo, fundidas por RRF)."""

import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import SearchMode
from app.models import Chunk, Document
from app.providers import get_embeddings

RRF_K = 60  # constante usual da Reciprocal Rank Fusion
CANDIDATES_FACTOR = 4

_TERM = re.compile(r"[\wÀ-ÿ]{2,}", re.UNICODE)


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    filename: str
    page: int
    content: str
    similarity: float  # similaridade de cosseno, 0 a 1
    score: float  # pontuação final usada na ordenação


def build_or_tsquery(question: str) -> str | None:
    """'qual a pressão máxima?' -> 'qual | pressão | máxima'.

    plainto_tsquery exige todas as palavras (AND), o que quase nunca casa com uma pergunta
    em linguagem natural. Com OR, o ts_rank decide quem tem mais termos em comum.
    """
    terms = sorted(set(t.lower() for t in _TERM.findall(question)))
    return " | ".join(terms) if terms else None


def _vector_ranking(session: Session, qvec: list[float], limit: int, doc_ids: list[int] | None):
    distance = Chunk.embedding.cosine_distance(qvec)
    stmt = select(Chunk.id, distance.label("distance")).order_by(distance).limit(limit)
    if doc_ids:
        stmt = stmt.where(Chunk.document_id.in_(doc_ids))
    return [(row.id, 1.0 - float(row.distance)) for row in session.execute(stmt)]


def _text_ranking(session: Session, question: str, limit: int, doc_ids: list[int] | None) -> list[int]:
    query_text = build_or_tsquery(question)
    if not query_text:
        return []
    tsq = func.to_tsquery("portuguese", query_text)
    rank = func.ts_rank_cd(Chunk.tsv, tsq)
    stmt = select(Chunk.id).where(Chunk.tsv.op("@@")(tsq)).order_by(rank.desc()).limit(limit)
    if doc_ids:
        stmt = stmt.where(Chunk.document_id.in_(doc_ids))
    return [row.id for row in session.execute(stmt)]


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for position, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + position)
    return scores


def retrieve(
    session: Session,
    question: str,
    top_k: int,
    mode: SearchMode = "hybrid",
    document_ids: list[int] | None = None,
) -> list[RetrievedChunk]:
    qvec = get_embeddings().embed_query(question)
    candidates = top_k * CANDIDATES_FACTOR
    vector = _vector_ranking(session, qvec, candidates, document_ids)
    similarity = dict(vector)

    if mode == "hybrid":
        fused = reciprocal_rank_fusion(
            [[cid for cid, _ in vector], _text_ranking(session, question, candidates, document_ids)]
        )
    else:
        fused = similarity

    top_ids = sorted(fused, key=fused.get, reverse=True)[:top_k]
    if not top_ids:
        return []

    rows = session.execute(
        select(Chunk, Document.filename, (1.0 - Chunk.embedding.cosine_distance(qvec)).label("sim"))
        .join(Document)
        .where(Chunk.id.in_(top_ids))
    ).all()
    by_id = {chunk.id: (chunk, filename, sim) for chunk, filename, sim in rows}

    return [
        RetrievedChunk(
            chunk_id=cid,
            document_id=by_id[cid][0].document_id,
            filename=by_id[cid][1],
            page=by_id[cid][0].page,
            content=by_id[cid][0].content,
            similarity=round(float(by_id[cid][2]), 4),
            score=round(fused[cid], 6),
        )
        for cid in top_ids
    ]
