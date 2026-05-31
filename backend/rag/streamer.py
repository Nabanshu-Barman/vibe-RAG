"""
rag/streamer.py
----------------
SSE (Server-Sent Events) formatter for the RAG streaming pipeline.

SSE wire format (per spec):
    data: {"type": "token", "content": "word "}\n\n
    data: {"type": "citations", "citations": [...]}\n\n
    data: {"type": "done"}\n\n

The double newline (\n\n) is mandatory — it signals the end of one event
to the browser's EventSource API.

Frontend consumption:
    const es = new EventSource('/api/chat', {...})
    es.onmessage = (e) => {
        const event = JSON.parse(e.data)
        if (event.type === 'token') appendToken(event.content)
        if (event.type === 'citations') showCitations(event.citations)
        if (event.type === 'done') es.close()
    }

Why StreamingResponse over WebSockets:
    - SSE is unidirectional (server → client) — perfect for streaming text
    - Native browser support via EventSource, no library needed on frontend
    - Automatically reconnects if the connection drops
    - Works through HTTP/1.1 proxies without special config
    - WebSockets add bidirectional overhead we don't need
"""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from api.schemas import VideoMetadata
from rag.chain import stream_rag_response

logger = logging.getLogger(__name__)


async def sse_generator(
    session_id: str,
    question: str,
    video_a: VideoMetadata,
    video_b: VideoMetadata,
) -> AsyncGenerator[str, None]:
    """
    Wrap stream_rag_response() events as SSE-formatted strings.
    Each yield is one complete SSE event ready to send over the wire.
    """
    try:
        async for event in stream_rag_response(session_id, question, video_a, video_b):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    except Exception as exc:
        logger.error("[SSE] Unhandled error in stream for session %s: %s", session_id, exc)
        error_event = {"type": "error", "content": str(exc)}
        yield f"data: {json.dumps(error_event)}\n\n"
        yield 'data: {"type": "done"}\n\n'
