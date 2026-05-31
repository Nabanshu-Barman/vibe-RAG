from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── API Keys ───────────────────────────────────────────────────────────────
    gemini_api_key: str
    youtube_api_key: str

    # ── ChromaDB ───────────────────────────────────────────────────────────────
    chroma_persist_dir: str = "./chroma_db"

    # ── Whisper ────────────────────────────────────────────────────────────────
    # "tiny" for speed on CPU; upgrade to "base" for better accuracy
    whisper_model: str = "tiny"

    # ── Embeddings ────────────────────────────────────────────────────────────
    # "gemini" uses the Gemini API; "local" uses sentence-transformers
    embedding_backend: str = "gemini"
    local_embedding_model: str = "sentence-transformers/bge-base-en-v1.5"
    local_embedding_device: str = "cpu"
    local_embedding_batch_size: int = 32
    local_embedding_normalize: bool = True

    # ── Chunking ───────────────────────────────────────────────────────────────
    # 512 chars ≈ 40s of speech — sweet spot for transcript RAG
    # See README §6 for full chunk size reasoning
    chunk_size: int = 512
    chunk_overlap: int = 64

    # ── Memory ─────────────────────────────────────────────────────────────────
    # Keep last k turns in context; at scale replace with Redis + TTL
    memory_window_k: int = 6

    # ── CORS ───────────────────────────────────────────────────────────────────
    frontend_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton. Use this everywhere instead of
    constructing Settings() directly — avoids re-reading .env on every call."""
    return Settings()


# Module-level singleton for convenience imports:  from core.config import settings
settings = get_settings()
