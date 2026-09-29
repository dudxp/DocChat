"""Fábrica de modelos: o resto do código não sabe se está falando com OpenAI, Ollama ou o provedor fake."""

import hashlib
import math
import re
import unicodedata
from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.prompt_values import PromptValue
from langchain_core.runnables import Runnable, RunnableLambda

from app.core.config import Settings, get_settings

_WORD = re.compile(r"\w+", re.UNICODE)


def normalize_words(text: str) -> list[str]:
    """Minúsculas, sem acento e com um radical grosseiro; suficiente para o provedor fake."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return [w[:6] for w in _WORD.findall(text) if len(w) > 2]


class HashingEmbeddings(Embeddings):
    """Embeddings determinísticos por hashing de palavras.

    Não entendem sinônimos, mas palavras em comum aproximam os vetores. Isso basta para os
    testes e para rodar o projeto sem chave de API nem modelo local.
    """

    def __init__(self, dim: int):
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for word in normalize_words(text):
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0 if (h >> 8) % 2 == 0 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


_SOURCE_BLOCK = re.compile(r"^\[(\d+)\][^\n]*\n(.+?)(?=\n\n\[\d+\]|\n\nPergunta:|\Z)", re.S | re.M)


def _fake_answer(prompt: PromptValue) -> AIMessage:
    """Resposta extrativa: a frase dos trechos com mais palavras em comum com a pergunta, citando o trecho."""
    human = str(prompt.to_messages()[-1].content)
    question = set(normalize_words(human.rsplit("Pergunta:", 1)[-1]))
    best: tuple[int, str, str] | None = None
    for match in _SOURCE_BLOCK.finditer(human):
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join(match.group(2).split())):
            overlap = len(question & set(normalize_words(sentence)))
            if len(sentence) > 15 and (best is None or overlap > best[0]):
                best = (overlap, sentence, match.group(1))
    if best is None or best[0] == 0:
        return AIMessage(content="Não encontrei essa informação nos documentos enviados.")
    return AIMessage(content=f"{best[1]} [{best[2]}]")


@lru_cache
def get_embeddings() -> Embeddings:
    s = get_settings()
    if s.llm_provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        kwargs = {"dimensions": s.embedding_dim} if s.embedding_dim else {}
        if s.openai_base_url:
            # APIs compatíveis (LM Studio, OpenRouter…) esperam texto, não os tokens do tiktoken.
            kwargs["check_embedding_ctx_length"] = False
        return OpenAIEmbeddings(
            model=s.openai_embedding_model,
            api_key=s.openai_api_key,
            base_url=s.openai_base_url,
            **kwargs,
        )
    if s.llm_provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=s.ollama_embedding_model, base_url=s.ollama_base_url)
    return HashingEmbeddings(s.vector_dim)


@lru_cache
def get_chat_model() -> BaseChatModel | Runnable:
    s = get_settings()
    return build_chat_model(s)


def build_chat_model(s: Settings, temperature: float = 0.0) -> BaseChatModel | Runnable:
    if s.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=s.openai_chat_model,
            api_key=s.openai_api_key,
            base_url=s.openai_base_url,
            temperature=temperature,
        )
    if s.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=s.ollama_chat_model, base_url=s.ollama_base_url, temperature=temperature)
    return RunnableLambda(_fake_answer)


def is_fake() -> bool:
    return get_settings().llm_provider == "fake"
