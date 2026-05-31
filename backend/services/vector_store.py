"""
services/vector_store.py
--------------------------
ChromaDB session collection manager.

Architecture decisions:
  - One Chroma collection per session (collection_name = "session_{uuid}")
  - Both videos' chunks live in the same collection, tagged with video_id metadata
  - This enables both cross-video comparison queries (no filter) and
    video-specific queries (filter: where={"video_id": "A"})
  - persist_directory ensures data survives server restarts during a session
  - DELETE /api/session/{id} calls delete_session() to clean up disk space

Retriever config:
  - k=4 returns ~2 chunks per video on average for a 2-video session
  - MMR (Maximal Marginal Relevance) would reduce redundancy but requires more
    Chroma API surface — plain similarity is sufficient for demo scale

Scalability note:
  At 10,000+ concurrent users, replace with Qdrant (Docker) or Pinecone.
  The LangChain Retriever interface is identical — zero downstream code changes.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever

from core.config import settings
from services.embedder import get_embedder

logger = logging.getLogger(__name__)

# ── Embedding batch config ────────────────────────────────────────────────────
# Gemini embedding free tier: 100 requests/minute (each text = 1 request).
# Sending 50 texts/batch with a 1.5s inter-batch pause keeps us comfortably
# under the limit even for sessions with 160 total chunks (2 batches × 80 each).
_EMBED_BATCH_SIZE = 50
_INTER_BATCH_PAUSE = 1.5   # seconds between batches
_MAX_EMBED_RETRIES = 3


# ── Collection accessor ───────────────────────────────────────────────────────

def _get_collection(session_id: str) -> Chroma:
    """
    Return a Chroma collection bound to this session.
    ChromaDB creates the collection on first use and persists it to disk.
    """
    return Chroma(
        collection_name=f"session_{session_id}",
        embedding_function=get_embedder(),
        persist_directory=os.path.abspath(settings.chroma_persist_dir),
    )


def _parse_retry_delay(exc_str: str, default: int = 65) -> int:
    """Extract 'retry in Ns' from a quota error string, adding a 5s buffer."""
    m = re.search(r"retry in\s+(\d+)", exc_str, re.IGNORECASE)
    if m:
        return int(m.group(1)) + 5
    return default


# ── Write ─────────────────────────────────────────────────────────────────────

def store_documents(docs: list[Document], session_id: str) -> int:
    """
    Embed and store all documents in batches to avoid hitting the Gemini
    free-tier embedding rate limit (100 requests/minute).

    Strategy:
      - Splits docs into batches of _EMBED_BATCH_SIZE (50).
      - Sleeps _INTER_BATCH_PAUSE (1.5s) between batches.
      - On 429/RESOURCE_EXHAUSTED, waits the suggested retry delay + 5s buffer,
        then retries up to _MAX_EMBED_RETRIES (3) times before re-raising.

    Called via asyncio.to_thread() so the event loop is never blocked.
    """
    if not docs:
        logger.warning("store_documents called with empty doc list for session %s", session_id)
        return 0

    collection = _get_collection(session_id)
    total = len(docs)

    for batch_start in range(0, total, _EMBED_BATCH_SIZE):
        batch = docs[batch_start : batch_start + _EMBED_BATCH_SIZE]
        batch_end = min(batch_start + _EMBED_BATCH_SIZE, total)
        logger.info(
            "[VectorStore] Session %s: embedding docs %d-%d / %d",
            session_id, batch_start + 1, batch_end, total,
        )

        for attempt in range(_MAX_EMBED_RETRIES):
            try:
                collection.add_documents(batch)
                break   # success
            except Exception as exc:
                exc_str = str(exc)
                is_quota = (
                    "429" in exc_str
                    or "RESOURCE_EXHAUSTED" in exc_str
                    or "quota" in exc_str.lower()
                )
                if is_quota and attempt < _MAX_EMBED_RETRIES - 1:
                    wait = _parse_retry_delay(exc_str)
                    logger.warning(
                        "[VectorStore] 429 quota exceeded — waiting %ds before retry %d/%d",
                        wait, attempt + 1, _MAX_EMBED_RETRIES - 1,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "[VectorStore] Embedding failed for session %s batch %d-%d: %s",
                        session_id, batch_start + 1, batch_end, exc,
                    )
                    raise

        # Pause between batches to stay within the rate limit
        if batch_end < total:
            time.sleep(_INTER_BATCH_PAUSE)

    count = collection._collection.count()  # noqa: protected-access
    logger.info(
        "[VectorStore] Session %s: stored %d chunks (%d total in collection)",
        session_id, total, count,
    )
    return count



# ── Read ──────────────────────────────────────────────────────────────────────

def get_retriever(
    session_id: str,
    k: int = 4,
    video_id: str | None = None,
) -> VectorStoreRetriever:
    """
    Return a similarity retriever for the session.

    Args:
        session_id: The session's UUID hex string.
        k:          Number of chunks to retrieve per query (default 4 → ~2 per video).
        video_id:   If set ("A" or "B"), restrict retrieval to that video's chunks.
                    Leave None for cross-video comparison queries.
    """
    collection = _get_collection(session_id)
    search_kwargs: dict = {"k": k}
    if video_id:
        search_kwargs["filter"] = {"video_id": video_id}

    return collection.as_retriever(
        search_type="similarity",
        search_kwargs=search_kwargs,
    )


def collection_count(session_id: str) -> int:
    """Return the total number of chunks stored for a session."""
    return _get_collection(session_id)._collection.count()  # noqa


# ── Delete ────────────────────────────────────────────────────────────────────

async def delete_session(session_id: str) -> bool:
    """
    Delete the ChromaDB collection for a session (called by DELETE /api/session/{id}).
    Runs in a thread because ChromaDB disk I/O is synchronous.
    """
    def _delete():
        try:
            _get_collection(session_id).delete_collection()
            logger.info("[VectorStore] Deleted collection for session %s", session_id)
            return True
        except Exception as exc:
            logger.error("Failed to delete collection for session %s: %s", session_id, exc)
            return False

    return await asyncio.to_thread(_delete)
