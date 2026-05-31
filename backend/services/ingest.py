"""
services/ingest.py
-------------------
Orchestrates the full video data pipeline:

  Phase 2 (data fetch):
    fetch_video_data(yt_url, ig_url)
      ├── YouTube: transcript + metadata (concurrent)
      └── Instagram: transcript + metadata (concurrent)
    Both platforms run concurrently via asyncio.gather.
    Returns two populated VideoMetadata objects.

  Phase 3 (chunk → embed → store):
    run_ingestion(yt_url, ig_url)
      ├── fetch_video_data()          [Phase 2]
      ├── chunk_transcript()          [RecursiveCharacterTextSplitter, 512 chars, 64 overlap]
      ├── store_documents()           [text-embedding-004 → ChromaDB]
      └── returns (VideoMetadata A, VideoMetadata B, session_id)

Chunk labeling (for citations):
    Chunk 0           → "Hook (0-5s)"    first content, intro/hook
    Chunk 1..n-2      → "Chunk {i}"      body content
    Chunk n-1 (last)  → "Conclusion"     closing content

Chunk size rationale:
    512 chars ≈ 40-60 words ≈ 15-25 seconds of speech.
    Large enough to carry a complete thought; small enough for precise retrieval.
    Overlap of 64 chars prevents cutting sentences mid-thought at boundaries.
"""
from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from api.schemas import VideoMetadata
from services.transcript import youtube as yt_transcript
from services.transcript import instagram as ig_transcript
from services.metadata import youtube_meta
from services.metadata import instagram_meta
from services.vector_store import store_documents

logger = logging.getLogger(__name__)

# Maximum chunks stored per video.
# A 20-min YouTube video can produce 250+ chunks at 512-char size.
# Capping at 80 keeps total below 160 chunks (well within free-tier embedding quota)
# while still providing rich retrieval coverage across the full transcript.
_MAX_CHUNKS_PER_VIDEO = 80


# ── Engagement rate ────────────────────────────────────────────────────────────

def compute_engagement_rate(likes: int, comments: int, views: int | None) -> float | None:
    """
    Standard social media engagement rate: (likes + comments) / views × 100

    Returns:
        float  — computed ER when views is a positive integer
        None   — when views is None (platform did not expose view count, e.g. Instagram)
                 Callers must display this as "N/A", never as 0 or an estimate.

    Design note:
        0.0% (zero engagement) and None (unavailable) are semantically different.
        A None ER should never be compared numerically against another video's ER.
    """
    if views is None:
        return None     # data unavailable — display as N/A
    if views == 0:
        return 0.0      # explicitly zero views → zero engagement rate
    return round((likes + comments) / views * 100, 4)


# ── Chunking ──────────────────────────────────────────────────────────────────

def _derive_label(chunk_index: int, total_chunks: int) -> str:
    """
    Human-readable chunk label for citation display.
      0         → "Hook (0-5s)"   — the opening / hook content
      last      → "Conclusion"    — the closing content
      anything  → "Chunk {i}"    — body content
    """
    if chunk_index == 0:
        return "Hook (0-5s)"
    if chunk_index == total_chunks - 1:
        return "Conclusion"
    return f"Chunk {chunk_index}"


def chunk_transcript(video: VideoMetadata, session_id: str) -> list[Document]:
    """
    Split a video's transcript into overlapping chunks and wrap each as a
    LangChain Document with rich metadata for retrieval and citation.

    Chunk size: 512 chars (≈ 40-60 words ≈ 15-25s of speech)
    Overlap   : 64 chars  (prevents mid-sentence boundary cuts)

    Metadata fields per chunk:
        video_id    — "A" or "B" (used to filter retrieval per-video)
        session_id  — isolates chunks across concurrent sessions
        chunk_index — 0-based position in the transcript
        chunk_label — human-readable label for citations
        creator     — video creator name
        platform    — "youtube" or "instagram"
        title       — video title (for context in LLM prompt)
    """
    if not video.transcript:
        logger.warning("[Chunker] Empty transcript for video %s (%s)", video.id, video.title)
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings_chunk_size(),
        chunk_overlap=settings_chunk_overlap(),
        separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
        length_function=len,
    )

    raw_chunks: list[str] = splitter.split_text(video.transcript)
    total = len(raw_chunks)

    docs: list[Document] = []
    for i, chunk_text in enumerate(raw_chunks):
        label = _derive_label(i, total)
        doc = Document(
            page_content=chunk_text,
            metadata={
                "video_id":    video.id,
                "session_id":  session_id,
                "chunk_index": i,
                "chunk_label": label,
                "creator":     video.creator,
                "platform":    video.platform,
                "title":       video.title,
            },
        )
        docs.append(doc)

    logger.info(
        "[Chunker] Video %s (%s): %d chunks from %d chars transcript",
        video.id, video.platform, total, len(video.transcript),
    )
    return docs


def _get_chunk_config() -> tuple[int, int]:
    """Lazy import of settings to avoid circular import at module load."""
    from core.config import settings
    return settings.chunk_size, settings.chunk_overlap


def settings_chunk_size() -> int:
    return _get_chunk_config()[0]


def settings_chunk_overlap() -> int:
    return _get_chunk_config()[1]


# ── Platform detection ───────────────────────────────────────────────────────

def detect_platform(url: str) -> str:
    """
    Auto-detect whether a URL is a YouTube video or Instagram Reel.
    Returns 'youtube' or 'instagram'.
    Raises VideoFetchError for unrecognised URLs (should never happen if Pydantic
    validation in AnalyzeRequest passed).
    """
    from core.exceptions import VideoFetchError  # lazy import avoids circular dep
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "instagram.com" in u:
        return "instagram"
    raise VideoFetchError(f"Cannot determine platform from URL: {url}")


# ── Phase 2 — per-platform pipelines ─────────────────────────────────────────

async def _fetch_youtube_data(url: str, video_id: str) -> dict:
    """Fetch YouTube transcript + metadata concurrently."""
    logger.info("[YouTube] Starting fetch for video_id=%s", video_id)

    async def _safe_transcript_fetch():
        from core.exceptions import TranscriptUnavailableError
        try:
            segments = await asyncio.to_thread(yt_transcript.fetch_transcript, video_id)
            full_transcript = yt_transcript.get_full_transcript(segments)
            hook_transcript = yt_transcript.get_hook_transcript(segments, seconds=5.0)
            return full_transcript, hook_transcript, segments
        except TranscriptUnavailableError as e:
            logger.warning("[YouTube] Native transcript API failed (%s). Falling back to Whisper via yt-dlp...", e)
            return await ig_transcript.fetch_transcript(url)

    transcript_task = _safe_transcript_fetch()
    metadata_task = youtube_meta.fetch_metadata(video_id, url)

    (full_transcript, hook_transcript, _segments), meta = await asyncio.gather(
        transcript_task, metadata_task
    )

    logger.info(
        "[YouTube] Done: '%s' | %d chars | hook: '%s...'",
        meta.get("title", "")[:40], len(full_transcript), hook_transcript[:60],
    )
    return {**meta, "transcript": full_transcript, "hook_transcript": hook_transcript}


async def _fetch_instagram_data(url: str) -> dict:
    """Fetch Instagram transcript + metadata concurrently."""
    logger.info("[Instagram] Starting fetch for %s", url)

    transcript_task = ig_transcript.fetch_transcript(url)
    metadata_task = instagram_meta.fetch_metadata(url)

    (full_transcript, hook_transcript, _segments), meta = await asyncio.gather(
        transcript_task, metadata_task
    )

    logger.info(
        "[Instagram] Done: '%s' | %d chars | hook: '%s...'",
        meta.get("title", "")[:40], len(full_transcript), hook_transcript[:60],
    )
    return {**meta, "transcript": full_transcript, "hook_transcript": hook_transcript}


# ── Phase 2 deliverable ───────────────────────────────────────────────────────

async def fetch_video_data(
    url_a: str,
    url_b: str,
) -> tuple[VideoMetadata, VideoMetadata]:
    """
    Fetch and populate full metadata + transcripts for both videos.
    Accepts any combination of YouTube and Instagram URLs.
    Platform is auto-detected from each URL.
    Both pipelines run CONCURRENTLY via asyncio.gather.
    """
    platform_a = detect_platform(url_a)
    platform_b = detect_platform(url_b)

    logger.info(
        "Starting concurrent fetch: A=%s(%s) | B=%s(%s)",
        platform_a.upper(),
        url_a[:60],
        platform_b.upper(),
        url_b[:60],
    )

    async def _fetch_a():
        if platform_a == "youtube":
            vid_id = yt_transcript.extract_video_id(url_a)
            return await _fetch_youtube_data(url_a, vid_id)
        return await _fetch_instagram_data(url_a)

    async def _fetch_b():
        if platform_b == "youtube":
            vid_id = yt_transcript.extract_video_id(url_b)
            return await _fetch_youtube_data(url_b, vid_id)
        return await _fetch_instagram_data(url_b)

    data_a, data_b = await asyncio.gather(_fetch_a(), _fetch_b())

    video_a = VideoMetadata(
        id="A",
        engagement_rate=compute_engagement_rate(
            data_a["likes"], data_a["comments"], data_a["views"]
        ),
        **data_a,
    )
    video_b = VideoMetadata(
        id="B",
        engagement_rate=compute_engagement_rate(
            data_b["likes"], data_b["comments"], data_b["views"]
        ),
        **data_b,
    )

    # Use %s with pre-formatted strings to avoid %.4f crash on None ER
    def _er_str(er: float | None) -> str:
        return f"{er:.4f}%" if er is not None else "N/A"

    logger.info(
        "Fetch complete — A (%s): %s ER | B (%s): %s ER",
        platform_a, _er_str(video_a.engagement_rate),
        platform_b, _er_str(video_b.engagement_rate),
    )
    return video_a, video_b



# ── Phase 3 deliverable ───────────────────────────────────────────────────────

async def run_ingestion(
    url_a: str,
    url_b: str,
) -> tuple[VideoMetadata, VideoMetadata, str]:
    """
    Full ingestion pipeline:
      1. fetch_video_data()     — transcript + metadata (auto-detects platform)
      2. chunk_transcript()     — split each transcript into 512-char chunks
      3. store_documents()      — embed (gemini-embedding-001) + store (ChromaDB)

    Returns:
        video_a    — VideoMetadata for URL A
        video_b    — VideoMetadata for URL B
        session_id — UUID hex string identifying this session's ChromaDB collection
    """
    # ── Step 1: fetch ─────────────────────────────────────────────────────────
    video_a, video_b = await fetch_video_data(url_a, url_b)

    # ── Step 2: chunk ─────────────────────────────────────────────────────────
    session_id = uuid4().hex
    logger.info("[Ingest] Session %s — chunking transcripts...", session_id)

    docs_a = chunk_transcript(video_a, session_id)
    docs_b = chunk_transcript(video_b, session_id)

    # Cap chunks per video to stay within embedding API free-tier limits.
    # 80 chunks ≈ 40,000 chars of transcript — more than enough for deep RAG retrieval.
    if len(docs_a) > _MAX_CHUNKS_PER_VIDEO:
        logger.warning(
            "[Ingest] Video A has %d chunks — capping at %d to preserve embedding quota.",
            len(docs_a), _MAX_CHUNKS_PER_VIDEO,
        )
        docs_a = docs_a[:_MAX_CHUNKS_PER_VIDEO]
    if len(docs_b) > _MAX_CHUNKS_PER_VIDEO:
        logger.warning(
            "[Ingest] Video B has %d chunks — capping at %d to preserve embedding quota.",
            len(docs_b), _MAX_CHUNKS_PER_VIDEO,
        )
        docs_b = docs_b[:_MAX_CHUNKS_PER_VIDEO]

    all_docs = docs_a + docs_b
    logger.info(
        "[Ingest] Session %s — total chunks: %d (A: %d, B: %d)",
        session_id, len(all_docs), len(docs_a), len(docs_b),
    )

    # ── Step 3: embed + store (blocking I/O → thread) ─────────────────────────
    logger.info("[Ingest] Session %s — embedding + storing in ChromaDB...", session_id)
    total_stored = await asyncio.to_thread(store_documents, all_docs, session_id)
    logger.info(
        "[Ingest] Session %s — ingestion complete. %d chunks in ChromaDB.",
        session_id, total_stored,
    )

    return video_a, video_b, session_id
