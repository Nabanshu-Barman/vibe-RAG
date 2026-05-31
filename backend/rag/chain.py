"""
rag/chain.py
--------------
RAG chain with per-session conversation memory and Gemini Flash streaming.

Architecture:
  1. Retrieve k=4 relevant chunks from ChromaDB (via vector_store.get_retriever)
  2. Build a context string from retrieved docs with [Video X - Label] citations
  3. Build the full prompt: system context + conversation history + new question
  4. Stream the response from Gemini 1.5 Flash token-by-token via .astream()
  5. Save the (question, answer) pair to per-session ConversationBufferWindowMemory
  6. Yield the citations as a final structured event

Memory strategy:
  ConversationBufferWindowMemory(k=6) keeps the last 6 turns.
  Stored in a module-level dict — survives hot reloads but resets on restart.
  This is intentional: sessions are ephemeral by design.
  At 10,000 users: swap dict → Redis with TTL=3600.

LLM choice: gemini-2.0-flash
  - Supports streaming natively via LangChain's .astream()
  - Free tier: 1,500 req/day, 1M tokens/min
  - temperature=0.3: factual but not robotic (0=boring, 0.7=hallucination risk)
"""
from __future__ import annotations

import asyncio
import logging
import warnings
from typing import AsyncGenerator

warnings.filterwarnings("ignore", category=FutureWarning, module="langchain_google_genai")

from langchain.memory import ConversationBufferWindowMemory
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from api.schemas import VideoMetadata
from core.config import settings
from services.vector_store import get_retriever

logger = logging.getLogger(__name__)


# ── Per-session memory store ──────────────────────────────────────────────────
# dict[session_id] → ConversationBufferWindowMemory
# Reset on server restart (intentional — sessions are ephemeral)
_memories: dict[str, ConversationBufferWindowMemory] = {}


def get_or_create_memory(session_id: str) -> ConversationBufferWindowMemory:
    """
    Return the existing memory for a session, or create a fresh one.
    k=MEMORY_WINDOW_K keeps the last N turns to avoid context overflow.
    return_messages=True stores as LangChain message objects (HumanMessage, AIMessage).
    """
    if session_id not in _memories:
        _memories[session_id] = ConversationBufferWindowMemory(
            k=settings.memory_window_k,
            return_messages=True,
            memory_key="chat_history",
            input_key="input",
            output_key="output",
        )
        logger.info("[Memory] Created new memory for session %s", session_id)
    return _memories[session_id]


def clear_memory(session_id: str) -> None:
    """Remove memory for a session (called by DELETE /api/session/{id})."""
    _memories.pop(session_id, None)
    logger.info("[Memory] Cleared memory for session %s", session_id)


# ── LLM singleton ─────────────────────────────────────────────────────────────

_llm: ChatGoogleGenerativeAI | None = None


def get_llm() -> ChatGoogleGenerativeAI:
    """
    Return a cached Gemini Flash instance.
    temperature=0.3: analytical responses without hallucination risk.
    streaming=True: required for .astream() to yield tokens incrementally.
    """
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash",
            google_api_key=settings.gemini_api_key,
            temperature=0.3,
            streaming=True,
        )
        logger.info("[LLM] Gemini 3.5 Flash initialised.")
    return _llm


# ── Prompt construction ───────────────────────────────────────────────────────

_VIDEO_BLOCK = """\
━━━ VIDEO {label} ({platform}) ━━━
Title      : {title}
Creator    : @{creator}
Followers  : {followers}
Views      : {views}
Likes      : {likes}
Comments   : {comments}
Eng. Rate  : {er}
Duration   : {duration}
Uploaded   : {date}
Hook       : "{hook}"\
"""

# Per-case comparison strategy injected into every prompt
_CASE_INSTRUCTIONS = {
    "YT_VS_YT": """\
━━━ COMPARISON STRATEGY (YouTube vs YouTube) ━━━
Both videos have views, so engagement rates ARE comparable.
• Compare engagement rates directly using the numbers above.
• Also compare: views, likes, comments, follower counts, hook effectiveness,
  transcript content, storytelling structure, posting style, and creator strategy.
• Cite specific numbers when making comparisons.\
""",

    "IG_VS_IG": """\
━━━ COMPARISON STRATEGY (Instagram vs Instagram) ━━━
Instagram does not expose view counts for these Reels.
• DO NOT use or reference engagement rate — it cannot be computed.
• DO NOT estimate, infer, or fabricate view counts or engagement rates.
• Compare using: likes, comments, hook effectiveness, transcript content,
  storytelling, pacing, call-to-actions, hashtags, creator messaging,
  and audience interaction signals.
• If asked about engagement rate, state clearly: "Engagement rate is unavailable
  because Instagram did not expose view counts for these Reels."\
""",

    "YT_VS_IG": """\
━━━ COMPARISON STRATEGY (YouTube vs Instagram) ━━━
These are cross-platform videos. Data availability differs:
• YouTube engagement rate IS available — you may reference it.
• Instagram engagement rate is N/A (view count not exposed by platform).
• DO NOT claim one video numerically outperformed the other using engagement rate.
• DO NOT use likes as a proxy for views on Instagram.
• DO NOT estimate, infer, or fabricate Instagram view counts or engagement rates.
• When views or follower counts show "N/A", acknowledge this honestly.
• Compare using all available evidence:
  – Hook effectiveness (both videos)
  – Transcript content and retrieved RAG chunks
  – Storytelling structure and pacing
  – Call-to-actions
  – Audience interaction signals (likes and comments where available)
  – Content strategy and creator messaging
  – Hashtag usage
  – YouTube: views, ER, subscriber count (all available)
  – Instagram: likes, comments (views and followers may be N/A)\
""",
}

_SYSTEM_HEADER = """\
You are VibeRAG, an expert social media content strategist and video analyst.
Your job is to compare two videos and provide precise, evidence-based insights.\
"""

_INSTRUCTIONS_FOOTER = """\
━━━ ANSWER RULES ━━━
- Base your answer on the retrieved context and the stats shown above.
- Always cite sources like [Video A - Hook (0-5s)] or [Video B - Chunk 2].
- Be specific and analytical. Avoid vague or generic statements.
- If a metric shows "N/A", acknowledge it — never estimate or fabricate it.
- Keep responses concise: 100-250 words unless a longer answer is clearly needed.\
"""


def _fmt_num(n: int | None) -> str:
    """Format a number for display, returning 'N/A' for None."""
    if n is None:
        return "N/A"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_er(er: float | None, views: int | None) -> str:
    """
    Format engagement rate for display.
    Returns 'N/A — view count not exposed by platform' when either er or views is None.
    Never returns a numeric string when data was unavailable.
    """
    if er is None or views is None:
        return "N/A — view count not exposed by platform"
    return f"{er:.2f}%"


def _comparison_case(video_a: VideoMetadata, video_b: VideoMetadata) -> str:
    """Determine which of the 3 comparison cases applies."""
    if video_a.platform == "youtube" and video_b.platform == "youtube":
        return "YT_VS_YT"
    if video_a.platform == "instagram" and video_b.platform == "instagram":
        return "IG_VS_IG"
    return "YT_VS_IG"


def _build_context(docs: list[Document]) -> str:
    """Format retrieved docs as labelled context blocks."""
    if not docs:
        return "(No relevant transcript sections found.)"
    parts = []
    for doc in docs:
        vid   = doc.metadata.get("video_id", "?")
        label = doc.metadata.get("chunk_label", "?")
        parts.append(f"[Video {vid} — {label}]\n{doc.page_content.strip()}")
    return "\n\n".join(parts)


def _format_history(messages: list[BaseMessage]) -> str:
    """Convert LangChain message objects to a readable conversation string."""
    if not messages:
        return "(No prior conversation.)"
    lines = []
    for msg in messages:
        role = "Human" if msg.type == "human" else "Assistant"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


def _build_full_prompt(
    video_a: VideoMetadata,
    video_b: VideoMetadata,
    context: str,
    history: list[BaseMessage],
    question: str,
) -> str:
    """
    Assemble the complete prompt string passed to Gemini.
    Automatically detects the comparison case (YT/YT, IG/IG, YT/IG) and
    injects the correct comparison strategy instructions.
    All None values are formatted as 'N/A' — never passed as raw None.
    """
    case = _comparison_case(video_a, video_b)

    block_a = _VIDEO_BLOCK.format(
        label     = "A",
        platform  = video_a.platform.capitalize(),
        title     = video_a.title[:80],
        creator   = video_a.creator,
        followers = _fmt_num(video_a.follower_count),
        views     = _fmt_num(video_a.views),
        likes     = _fmt_num(video_a.likes),
        comments  = _fmt_num(video_a.comments),
        er        = _fmt_er(video_a.engagement_rate, video_a.views),
        duration  = video_a.duration,
        date      = video_a.upload_date,
        hook      = video_a.hook_transcript[:120],
    )

    block_b = _VIDEO_BLOCK.format(
        label     = "B",
        platform  = video_b.platform.capitalize(),
        title     = video_b.title[:80],
        creator   = video_b.creator,
        followers = _fmt_num(video_b.follower_count),
        views     = _fmt_num(video_b.views),
        likes     = _fmt_num(video_b.likes),
        comments  = _fmt_num(video_b.comments),
        er        = _fmt_er(video_b.engagement_rate, video_b.views),
        duration  = video_b.duration,
        date      = video_b.upload_date,
        hook      = video_b.hook_transcript[:120],
    )

    case_instructions = _CASE_INSTRUCTIONS[case]
    hist_section = (
        f"\n━━━ CONVERSATION HISTORY ━━━\n{_format_history(history)}\n"
        if history else ""
    )

    return (
        f"{_SYSTEM_HEADER}\n\n"
        f"{block_a}\n\n"
        f"{block_b}\n\n"
        f"{case_instructions}\n\n"
        f"━━━ RETRIEVED TRANSCRIPT CONTEXT ━━━\n{context}\n\n"
        f"{_INSTRUCTIONS_FOOTER}"
        f"{hist_section}\n\n"
        f"Human: {question}\nAssistant:"
    )



# ── Main streaming function ───────────────────────────────────────────────────

async def stream_rag_response(
    session_id: str,
    question: str,
    video_a: VideoMetadata,
    video_b: VideoMetadata,
) -> AsyncGenerator[dict, None]:
    """
    Full RAG pipeline with streaming. Yields dicts that are JSON-serialised as SSE events.

    Event types:
        {"type": "token",     "content": "word "}          — one streaming token
        {"type": "citations", "citations": [...]}           — retrieved chunk refs
        {"type": "done"}                                    — stream complete

    Flow:
        retrieve → build prompt → stream LLM → yield citations → save memory → done
    """
    # ── 1. Retrieve relevant chunks ───────────────────────────────────────────
    retriever = get_retriever(session_id, k=4)
    try:
        docs = await retriever.ainvoke(question)
    except Exception as exc:
        logger.error("[RAG] Retrieval failed for session %s: %s", session_id, exc)
        docs = []

    citations = [
        {
            "video_id":    d.metadata.get("video_id", "?"),
            "chunk_label": d.metadata.get("chunk_label", "?"),
            "chunk_index": d.metadata.get("chunk_index", 0),
            "platform":    d.metadata.get("platform", "?"),
            "creator":     d.metadata.get("creator", "?"),
            "excerpt":     d.page_content[:120],
        }
        for d in docs
    ]

    context_str = _build_context(docs)
    logger.info(
        "[RAG] Session %s — retrieved %d chunks for query: '%s...'",
        session_id, len(docs), question[:50],
    )

    # ── 2. Load conversation history ──────────────────────────────────────────
    memory = get_or_create_memory(session_id)
    history_msgs: list[BaseMessage] = memory.load_memory_variables({}).get("chat_history", [])

    # ── 3. Build full prompt ──────────────────────────────────────────────────
    prompt = _build_full_prompt(video_a, video_b, context_str, history_msgs, question)

    # ── 4. Stream LLM response token by token ─────────────────────────────────
    llm = get_llm()
    full_response = ""
    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            async for chunk in llm.astream(prompt):
                token = chunk.content
                if token:
                    full_response += token
                    yield {"type": "token", "content": token}
            break  # success — exit retry loop
        except Exception as exc:
            exc_str = str(exc)
            is_rate_limit = "429" in exc_str or "quota" in exc_str.lower()
            if is_rate_limit and attempt < max_retries:
                wait = 60 * (attempt + 1)  # 60s, then 120s
                logger.warning(
                    "[RAG] 429 rate limit — waiting %ds before retry %d/%d",
                    wait, attempt + 1, max_retries,
                )
                yield {"type": "token", "content": f"\n\n[Rate limited — retrying in {wait}s...]"}
                await asyncio.sleep(wait)
                full_response = ""  # reset for retry
            else:
                logger.error("[RAG] LLM error for session %s: %s", session_id, exc)
                yield {"type": "token", "content": f"\n\n[Error: {exc}]"}
                break

    # ── 5. Citations ──────────────────────────────────────────────────────────
    yield {"type": "citations", "citations": citations}

    # ── 6. Save to memory ─────────────────────────────────────────────────────
    if full_response:
        memory.save_context(
            {"input": question},
            {"output": full_response},
        )
        logger.info(
            "[Memory] Saved turn for session %s (history depth: %d)",
            session_id,
            len(memory.chat_memory.messages),
        )

    # ── 7. Done ───────────────────────────────────────────────────────────────
    yield {"type": "done"}
