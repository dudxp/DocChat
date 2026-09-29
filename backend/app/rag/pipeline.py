"""Pipeline de pergunta e resposta: reescreve a pergunta, busca os trechos, gera a resposta e extrai as citações."""

import re
import time
from dataclasses import dataclass, field

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.orm import Session

from app.core.config import SearchMode, get_settings
from app.domain.access import Access
from app.rag.providers import get_chat_model, is_fake
from app.rag.retrieval import RetrievedChunk, retrieve

NOT_FOUND = "Não encontrei essa informação nos documentos enviados."

ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Você responde perguntas usando SOMENTE os trechos de documentos fornecidos.\n"
            "Regras:\n"
            "- Depois de cada afirmação, cite o trecho que a sustenta no formato [n], por exemplo [2].\n"
            "- Não use conhecimento externo. Se os trechos não trazem a resposta, diga exatamente: "
            f'"{NOT_FOUND}"\n'
            "- Seja direto e responda no mesmo idioma da pergunta.",
        ),
        ("human", "Trechos:\n\n{context}\n\nPergunta: {question}"),
    ]
)

CONDENSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Reescreva a última pergunta do usuário para que ela seja compreensível sem o histórico. "
            "Mantenha o idioma. Responda apenas com a pergunta reescrita.",
        ),
        ("human", "Histórico:\n{history}\n\nÚltima pergunta: {question}"),
    ]
)

_CITATION = re.compile(r"\[(\d+)\]")


@dataclass
class Answer:
    question: str
    search_query: str
    answer: str
    sources: list[RetrievedChunk]
    cited: list[int] = field(default_factory=list)  # números [n] citados, base 1
    latency_ms: int = 0


def format_context(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[{i}] (documento: {c.filename}, {c.location})\n{c.content}" for i, c in enumerate(chunks, start=1)
    )


def extract_citations(text: str, num_sources: int) -> list[int]:
    seen: list[int] = []
    for match in _CITATION.finditer(text):
        n = int(match.group(1))
        if 1 <= n <= num_sources and n not in seen:
            seen.append(n)
    return seen


def condense_question(question: str, history: list[dict]) -> str:
    """Transforma 'e qual o prazo dela?' em uma pergunta que a busca consegue usar."""
    if not history or is_fake():
        return question
    lines = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
    chain = CONDENSE_PROMPT | get_chat_model() | StrOutputParser()
    return chain.invoke({"history": lines, "question": question}).strip() or question


def answer_question(
    session: Session,
    question: str,
    *,
    history: list[dict] | None = None,
    top_k: int | None = None,
    mode: SearchMode | None = None,
    document_ids: list[int] | None = None,
    access: Access | None = None,
) -> Answer:
    settings = get_settings()
    started = time.perf_counter()

    search_query = condense_question(question, history or [])
    chunks = retrieve(
        session,
        search_query,
        top_k=top_k or settings.top_k,
        mode=mode or settings.search_mode,
        document_ids=document_ids,
        access=access,
    )

    if not chunks:
        text = NOT_FOUND
    else:
        chain = ANSWER_PROMPT | get_chat_model() | StrOutputParser()
        text = chain.invoke({"context": format_context(chunks), "question": search_query}).strip()

    return Answer(
        question=question,
        search_query=search_query,
        answer=text,
        sources=chunks,
        cited=extract_citations(text, len(chunks)),
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
