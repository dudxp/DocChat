from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import ensure_admin
from app.config import get_settings
from app.db import init_db
from app.routers import admin, auth, chat, documents, evaluation
from app.schemas import HealthOut


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_admin()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DocChat",
        description="Perguntas e respostas sobre PDFs com citação de fonte e avaliação por gabarito.",
        version="1.0.0",
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
