"""
core/exceptions.py
-------------------
Plain Python exceptions for the service layer.
NO FastAPI dependency here — services must be importable without a web framework.

The API layer (main.py exception handlers) catches these and converts them
to the correct HTTP status codes. This keeps services testable standalone.
"""


class VibeRAGError(Exception):
    """Base exception for all VibeRAG domain errors."""
    def __init__(self, detail: str, status_code: int = 500):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class VideoFetchError(VibeRAGError):
    """Raised when a video URL cannot be fetched, is invalid, or is private."""
    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=400)


class TranscriptUnavailableError(VibeRAGError):
    """Raised when a video has transcripts disabled or no captions available."""
    def __init__(self, video_platform: str = "video"):
        super().__init__(
            detail=(
                f"Transcript unavailable for this {video_platform}. "
                "The video may have captions disabled or be in an unsupported language."
            ),
            status_code=400,
        )


class EmbedError(VibeRAGError):
    """Raised when the embedding API call fails."""
    def __init__(self, detail: str = "Failed to generate embeddings. Please try again."):
        super().__init__(detail=detail, status_code=503)


class QuotaExceededError(VibeRAGError):
    """Raised when an external API quota is exceeded (e.g. YouTube Data API v3)."""
    def __init__(self, service: str = "YouTube API"):
        super().__init__(
            detail=(
                f"{service} quota exceeded. "
                "The free tier allows 10,000 units/day. Try again tomorrow."
            ),
            status_code=429,
        )


class PrivateAccountError(VibeRAGError):
    """Raised when an Instagram account or post is private."""
    def __init__(self):
        super().__init__(
            detail="This Instagram account or reel is private and cannot be accessed.",
            status_code=400,
        )


class SessionNotFoundError(VibeRAGError):
    """Raised when a session_id does not exist in the store."""
    def __init__(self, session_id: str):
        super().__init__(
            detail=f"Session '{session_id}' not found. Analyze two videos first.",
            status_code=404,
        )
