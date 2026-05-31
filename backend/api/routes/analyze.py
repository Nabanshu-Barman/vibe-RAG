"""
api/routes/analyze.py
----------------------
POST /api/analyze — full ingestion pipeline endpoint.

Flow:
  1. Pydantic validates URLs (fast-fail 422, no external calls)
  2. run_ingestion() runs Phase 2+3 concurrently:
       YouTube transcript + metadata   ─┐  asyncio.gather
       Instagram audio + Whisper       ─┘
       → chunk → embed (gemini-embedding-001) → ChromaDB
  3. Returns AnalyzeResponse with both VideoMetadata + session_id

Typical latency:
  YouTube only:   ~3-5s   (transcript API + YouTube Data API)
  + Instagram:    ~25-40s  (yt-dlp download + Whisper CPU transcription)
  + Embedding:    ~2-4s    (9-15 chunks via Gemini API)
  Total:          ~30-50s

Error surfaces:
  400 VideoFetchError      — invalid URL, private video, unavailable
  400 TranscriptUnavailable — captions disabled or no audio detected
  400 PrivateAccountError  — private Instagram account
  429 QuotaExceeded        — YouTube Data API v3 daily quota hit
  503 EmbedError           — Gemini embedding API down
  422 (Pydantic)           — malformed URL format, missing fields
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from api.schemas import AnalyzeRequest, AnalyzeResponse
from services.ingest import run_ingestion

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze two videos",
    description=(
        "Accepts two video URLs (url_a and url_b) — any combination of YouTube and Instagram. "
        "Fetches transcripts + metadata for both, chunks and embeds the transcripts "
        "into a per-session ChromaDB collection, and returns full metadata for both videos "
        "along with a `session_id` to use in subsequent `/chat` requests."
    ),
    responses={
        200: {"description": "Analysis complete"},
        400: {"description": "Invalid URL, private video, or no captions"},
        422: {"description": "Malformed request body"},
        429: {"description": "External API quota exceeded"},
        503: {"description": "Embedding service unavailable"},
    },
)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    t0 = time.perf_counter()

    logger.info(
        "[Analyze] Request received — A: %s | B: %s",
        req.url_a[:70],
        req.url_b[:70],
    )

    # run_ingestion is fully async — YouTube + Instagram pipelines run concurrently
    # All domain errors (VideoFetchError, QuotaExceeded, etc.) bubble up to the
    # global VibeRAGError handler in main.py and become typed HTTP error responses.
    video_a, video_b, session_id = await run_ingestion(
        req.url_a,
        req.url_b,
    )

    elapsed = time.perf_counter() - t0
    logger.info(
        "[Analyze] Done in %.1fs — session=%s | A='%s...' | B='%s...'",
        elapsed,
        session_id,
        video_a.title[:35],
        video_b.title[:35],
    )

    return AnalyzeResponse(
        video_a=video_a,
        video_b=video_b,
        session_id=session_id,
    )
