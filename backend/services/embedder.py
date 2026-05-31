"""
services/embedder.py
----------------------
Google gemini-embedding-001 singleton via LangChain.

Why gemini-embedding-001 (formerly text-embedding-004):
  - Current stable Google embedding model via the Gemini API
  - Free with the Gemini API key already required for the LLM
  - task_type="retrieval_document" at index time → "retrieval_query" at query time
    gives measurable NDCG improvement over the default "SEMANTIC_SIMILARITY" mode

Available embedding models (as of May 2026):
  models/gemini-embedding-001          ← stable, we use this
  models/gemini-embedding-2-preview    ← preview, not used in production
  models/gemini-embedding-2            ← latest, same API surface

Scalability note (10,000 users):
  At scale, swap to locally-served bge-base-en-v1.5 via sentence-transformers.
  Zero ChromaDB re-indexing — just swap the embedding function.
"""
from __future__ import annotations

import logging
import warnings
from functools import lru_cache

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module="langchain_google_genai",
)

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings

from core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedder():
  """
  Return a cached embedder instance.
  Supports either Gemini embeddings (API) or local sentence-transformers.
  """
  backend = settings.embedding_backend.strip().lower()
  if backend == "local":
    logger.info(
      "Initialising local embedder: %s (device=%s)",
      settings.local_embedding_model,
      settings.local_embedding_device,
    )
    return HuggingFaceEmbeddings(
      model_name=settings.local_embedding_model,
      model_kwargs={"device": settings.local_embedding_device},
      encode_kwargs={
        "batch_size": settings.local_embedding_batch_size,
        "normalize_embeddings": settings.local_embedding_normalize,
      },
    )

  logger.info("Initialising Google gemini-embedding-2 embedder.")
  return GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-2",
    google_api_key=settings.gemini_api_key,
    task_type="retrieval_document",
  )

