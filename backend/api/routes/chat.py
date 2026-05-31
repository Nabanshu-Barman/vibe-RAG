"""
api/routes/chat.py
-------------------
POST /api/chat     — SSE streaming RAG response
DELETE /api/session/{session_id} — clean up ChromaDB + memory for a session
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from api.schemas import ChatRequest, SessionDeleteResponse
from core.exceptions import SessionNotFoundError
from rag.chain import clear_memory
from rag.streamer import sse_generator
from services.vector_store import delete_session as chroma_delete_session

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    """
    POST /api/chat

    Accepts a ChatRequest (session_id, message, video_a, video_b) and returns
    a Server-Sent Events stream. Each SSE event is a JSON-encoded ChatChunk:

        {"type": "token",     "content": "word "}          — streaming token
        {"type": "citations", "citations": [...]}           — source chunks
        {"type": "done"}                                    — stream finished

    The frontend should read this with EventSource or fetch + ReadableStream,
    accumulating tokens and rendering citations after the stream ends.

    Headers:
        Cache-Control: no-cache    — prevent proxy/CDN buffering
        X-Accel-Buffering: no      — disable nginx proxy buffering
        Connection: keep-alive     — required for SSE
    """
    logger.info(
        "[Chat] session=%s question='%s...'",
        req.session_id, req.message[:60],
    )

    return StreamingResponse(
        sse_generator(
            session_id=req.session_id,
            question=req.message,
            video_a=req.video_a,
            video_b=req.video_b,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.delete("/session/{session_id}")
async def delete_session(session_id: str) -> SessionDeleteResponse:
    """
    DELETE /api/session/{session_id}

    Cleans up all resources for a session:
      1. Delete ChromaDB collection (frees disk space)
      2. Clear in-memory ConversationBufferWindowMemory

    Called by the frontend when the user starts a new analysis or closes the app.
    Safe to call multiple times — returns success even if session doesn't exist.
    """
    logger.info("[Session] Deleting session %s", session_id)

    # Delete ChromaDB collection (runs in thread — blocking disk I/O)
    chroma_ok = await chroma_delete_session(session_id)

    # Clear in-process memory
    clear_memory(session_id)

    return SessionDeleteResponse(
        session_id=session_id,
        deleted=chroma_ok,
        message="Session deleted successfully." if chroma_ok else "Session not found or already deleted.",
    )
