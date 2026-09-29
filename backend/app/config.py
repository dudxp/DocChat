from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["openai", "ollama", "fake"]
SearchMode = Literal["vector", "hybrid"]

# Dimensão padrão dos embeddings de cada provedor, usada quando EMBEDDING_DIM não é informado.
DEFAULT_EMBEDDING_DIM: dict[str, int] = {
    "openai": 1536,  # text-embedding-3-small
    "ollama": 768,  # nomic-embed-text
    "fake": 256,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/docchat"

    llm_provider: Provider = "openai"

    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "nomic-embed-text"

    embedding_dim: int | None = None

    chunk_size: int = 1000
    chunk_overlap: int = 150
    top_k: int = 5
    search_mode: SearchMode = "hybrid"
    max_upload_mb: int = 25

    cors_origins: str = "http://localhost:5173"

    @property
    def vector_dim(self) -> int:
        return self.embedding_dim or DEFAULT_EMBEDDING_DIM[self.llm_provider]

    @property
    def chat_model_name(self) -> str:
        return {
            "openai": self.openai_chat_model,
            "ollama": self.ollama_chat_model,
            "fake": "fake-extractive",
        }[self.llm_provider]

    @property
    def embedding_model_name(self) -> str:
        return {
            "openai": self.openai_embedding_model,
            "ollama": self.ollama_embedding_model,
            "fake": "fake-hashing",
        }[self.llm_provider]


@lru_cache
def get_settings() -> Settings:
    return Settings()
