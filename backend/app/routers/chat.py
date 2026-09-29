from fastapi import APIRouter

from app.access import Access
from app.auth import CurrentUser
from app.db import SessionDep
from app.rag import answer_question
from app.schemas import ChatIn, ChatOut, SourceOut

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatOut)
def chat(body: ChatIn, user: CurrentUser, session: SessionDep):
    # A restrição de acesso vai para dentro da busca: trechos que o usuário não pode ver nem são recuperados.
    result = answer_question(
        session,
        body.question,
        history=[m.model_dump() for m in body.history],
        top_k=body.top_k,
        mode=body.search_mode,
        document_ids=body.document_ids,
        access=Access.for_user(user),
    )
    return ChatOut(
        answer=result.answer,
        search_query=result.search_query,
        latency_ms=result.latency_ms,
        sources=[
            SourceOut(
                number=i,
                document_id=s.document_id,
                filename=s.filename,
                page=s.page,
                content=s.content,
                similarity=s.similarity,
                cited=i in result.cited,
            )
            for i, s in enumerate(result.sources, start=1)
        ],
    )
