"""
main.py — VibeRAG FastAPI application entry point

Startup order:
  1. Suppress noisy library warnings (FutureWarning from langchain-google-genai,
     ChromaDB telemetry errors) so logs stay clean
  2. Configure structured logging
  3. Build FastAPI app with CORS + GZip + request timing middleware
  4. Register global VibeRAGError exception handler
  5. Mount /api routers
  6. Expose GET /health and GET /

Run:
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import logging
import os
import time
import warnings

# ── Silence noisy library warnings before any imports that trigger them ────────
# langchain-google-genai 2.0.7 imports the deprecated google.generativeai package
warnings.filterwarnings("ignore", category=FutureWarning, module="langchain_google_genai")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")
# ChromaDB telemetry capture() signature mismatch — cosmetic only, doesn't affect function
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.exceptions import VibeRAGError
from api.schemas import HealthResponse
from api.routes.analyze import router as analyze_router
from api.routes.chat import router as chat_router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("viberag")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="VibeRAG API",
    description=(
        "RAG-powered video comparison backend. "
        "Accepts a YouTube URL + Instagram Reel URL, fetches transcripts and metadata, "
        "chunks and embeds content into ChromaDB, then streams Gemini 2.5 Flash responses "
        "with source citations via Server-Sent Events.\n\n"
        "**Endpoints:**\n"
        "- `POST /api/analyze` — ingest both videos (returns session_id)\n"
        "- `POST /api/chat` — ask questions, streams SSE tokens + citations\n"
        "- `DELETE /api/session/{id}` — clean up ChromaDB + memory\n"
        "- `GET /health` — liveness probe"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Cache-Control"],
)

# GZip compresses responses > 1KB — saves bandwidth on large VideoMetadata JSON
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Structured per-request logging with method, path, status, and duration."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s → %d  (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(VibeRAGError)
async def viberag_error_handler(request: Request, exc: VibeRAGError) -> JSONResponse:
    """
    Global handler for all domain exceptions raised by the service layer.
    Services raise plain Python exceptions (no FastAPI dependency).
    This is the single place they are converted to HTTP responses.

    Subclasses handled:
      VideoFetchError         → 400
      TranscriptUnavailable   → 400
      PrivateAccountError     → 400
      QuotaExceededError      → 429
      EmbedError              → 503
      SessionNotFoundError    → 404
    """
    logger.warning(
        "Domain error [%d] on %s %s: %s",
        exc.status_code, request.method, request.url.path, exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(analyze_router, prefix="/api", tags=["Analysis"])
app.include_router(chat_router, prefix="/api", tags=["Chat"])


# ── Startup event ─────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info(
        "VibeRAG API v1.0.0 starting — "
        "LLM: gemini-3.5-flash | Embeddings: gemini-embedding-2 | "
        "Vector DB: ChromaDB @ %s | Frontend origin: %s",
        settings.chroma_persist_dir,
        settings.frontend_origin,
    )


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Liveness probe",
    description="Returns 200 if the server is running. Used by the frontend before analysis.",
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({
        "message": "VibeRAG API v1.0.0",
        "docs": "/docs",
        "health": "/health",
    })
