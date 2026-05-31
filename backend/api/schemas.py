from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, HttpUrl, field_validator


# ── Inbound ───────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """
    Accepts any combination of platforms in any order:
      YouTube + YouTube, Instagram + Instagram, YouTube + Instagram, Instagram + YouTube.
    The backend auto-detects the platform from each URL.
    """
    url_a: str   # Video A — YouTube or Instagram Reel URL
    url_b: str   # Video B — YouTube or Instagram Reel URL

    @field_validator("url_a", "url_b", mode="before")
    @classmethod
    def validate_social_url(cls, v: str) -> str:
        v = str(v).strip()
        is_yt = (
            "youtube.com/watch" in v
            or "youtu.be/" in v
            or "youtube.com/shorts/" in v
            or "youtube.com/embed/" in v
        )
        is_ig = "instagram.com/reel" in v or "instagram.com/p/" in v
        if not is_yt and not is_ig:
            raise ValueError(
                "Must be a valid YouTube video URL or Instagram Reel URL. "
                "Accepted formats: youtube.com/watch?v=..., youtu.be/..., "
                "youtube.com/shorts/..., "
                "instagram.com/reel/..., instagram.com/reels/..., instagram.com/p/..."
            )
        return v


class ChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    video_a: "VideoMetadata"   # full metadata for system prompt context
    video_b: "VideoMetadata"   # full metadata for system prompt context
    history: list[ChatHistoryItem] = []


# ── Outbound ──────────────────────────────────────────────────────────────────

class VideoMetadata(BaseModel):
    """Returned by POST /api/analyze — one per video. Mirrors the frontend VideoMetadata type."""
    id: Literal["A", "B"]
    platform: Literal["youtube", "instagram"]
    url: str
    title: str
    creator: str
    follower_count: Optional[int]
    thumbnail_url: str
    views: Optional[int]
    likes: int
    comments: int
    upload_date: str          # ISO 8601 date string: "2024-11-15"
    duration: str             # Human-readable: "12:47"
    hashtags: list[str]
    engagement_rate: Optional[float]    # (likes + comments) / views * 100, rounded to 4dp
    hook_transcript: str      # First ~5 seconds of spoken content
    transcript: str           # Full transcript text


class AnalyzeResponse(BaseModel):
    video_a: VideoMetadata
    video_b: VideoMetadata
    session_id: str


class Citation(BaseModel):
    video_id: Literal["A", "B"]
    chunk_label: str          # e.g. "Hook (0–5s)", "Chunk 3", "Conclusion"
    chunk_index: int


class ChatChunk(BaseModel):
    """One SSE event. Either carries a token OR the final citations+done signal."""
    token: Optional[str] = None
    citations: Optional[list[Citation]] = None
    done: Optional[bool] = None


class SessionDeleteResponse(BaseModel):
    session_id: str
    deleted: bool
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
