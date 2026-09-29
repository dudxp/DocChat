from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import ensure_admin
from app.api.routers import admin, auth, chat, documents, evaluation
from app.api.schemas import HealthOut
from app.core.config import get_settings
from app.core.db import init_db

DESCRIPTION = """
Perguntas e respostas sobre PDFs com **citação de fonte**, **controle de acesso por área** e
**avaliação por gabarito**.

## Autenticação

1. Faça login em `POST /api/auth/login` com usuário e senha (formulário OAuth2).
2. Envie o `access_token` recebido no cabeçalho `Authorization: Bearer <token>`.

Nesta página, use o botão de autenticação com usuário e senha: o token é obtido e enviado sozinho.

## Acesso

Cada documento é global ou compartilhado com algumas áreas. A lista de documentos, o download do PDF e
a busca do chat só enxergam o que o usuário logado pode ver. Rotas de escrita, administração e
avaliação exigem um administrador.
"""

TAGS = [
    {"name": "auth", "description": "Login e dados do usuário logado."},
    {"name": "chat", "description": "Perguntas sobre os documentos, com as fontes de cada resposta."},
    {"name": "documents", "description": "Envio, listagem, acesso e download dos PDFs."},
    {"name": "areas", "description": "Áreas da empresa, usadas para compartilhar documentos."},
    {"name": "users", "description": "Cadastro de usuários (somente administradores)."},
    {"name": "evaluation", "description": "Gabarito e execuções de avaliação (somente administradores)."},
    {"name": "health", "description": "Situação da API e modelos em uso."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_admin()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DocChat",
        description=DESCRIPTION,
        version="1.1.0",
        openapi_tags=TAGS,
        # Tudo sob /api, para abrir pelo mesmo endereço do front (nginx e Vite só repassam /api).
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(documents.router)
    app.include_router(chat.router)
    app.include_router(evaluation.router)

    @app.get("/api/health", response_model=HealthOut, tags=["health"])
    def health():
        return HealthOut(
            status="ok",
            provider=settings.llm_provider,
            chat_model=settings.chat_model_name,
            embedding_model=settings.embedding_model_name,
            search_mode=settings.search_mode,
            top_k=settings.top_k,
        )

    return app


app = create_app()
