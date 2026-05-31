"""
services/metadata/youtube_meta.py
-----------------------------------
Fetches YouTube video metadata via the YouTube Data API v3.

Cost: 1 quota unit per video (videos.list) + 1 unit for channel subscriber count.
Free quota: 10,000 units/day → ~5,000 video analyses/day on the free tier.

Fields fetched in a single videos.list call (part=snippet,statistics,contentDetails):
  snippet         → title, channelTitle, publishedAt, tags, thumbnails
  statistics      → viewCount, likeCount, commentCount
  contentDetails  → duration (ISO 8601)

Subscriber count requires a separate channels.list call using the channelId
returned by the snippet.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.config import settings
from core.exceptions import VideoFetchError, QuotaExceededError

logger = logging.getLogger(__name__)


# ── ISO 8601 duration parser ──────────────────────────────────────────────────

def parse_iso8601_duration(duration: str) -> str:
    """
    Convert ISO 8601 duration (PT1H2M47S) to human-readable string (1:02:47).
    YouTube's contentDetails.duration uses this format.

    Examples:
      PT12M47S  → "12:47"
      PT1H2M7S  → "1:02:07"
      PT58S     → "0:58"
    """
    match = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        duration or "",
    )
    if not match:
        return "0:00"

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


# ── YouTube API client ────────────────────────────────────────────────────────

def _build_client():
    """Build a YouTube Data API v3 client. Called once per request — not cached
    because googleapiclient handles connection pooling internally."""
    return build("youtube", "v3", developerKey=settings.youtube_api_key)


# ── Main fetch function ───────────────────────────────────────────────────────

async def fetch_metadata(video_id: str, url: str) -> dict:
    """
    Fetch all metadata for a YouTube video.
    Returns a dict matching the VideoMetadata schema fields.

    Raises:
        VideoFetchError: if the video doesn't exist or is private.
        QuotaExceededError: if the API quota is exhausted.
    """
    import asyncio
    return await asyncio.to_thread(_fetch_metadata_sync, video_id, url)


def _fetch_metadata_sync(video_id: str, url: str) -> dict:
    """Synchronous implementation — called via asyncio.to_thread."""
    try:
        youtube = _build_client()

        # ── Video details (1 quota unit) ─────────────────────────────────────
        video_resp = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=video_id,
        ).execute()

        items = video_resp.get("items", [])
        if not items:
            raise VideoFetchError(
                f"YouTube video '{video_id}' not found. It may be private or deleted."
            )

        item = items[0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})

        channel_id = snippet.get("channelId", "")
        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))

        # Parse upload date to YYYY-MM-DD
        raw_date = snippet.get("publishedAt", "")
        try:
            upload_date = datetime.fromisoformat(
                raw_date.replace("Z", "+00:00")
            ).strftime("%Y-%m-%d")
        except Exception:
            upload_date = raw_date[:10] if raw_date else ""

        # ── Subscriber count (1 quota unit) ──────────────────────────────────
        follower_count = 0
        if channel_id:
            ch_resp = youtube.channels().list(
                part="statistics",
                id=channel_id,
            ).execute()
            ch_items = ch_resp.get("items", [])
            if ch_items:
                follower_count = int(
                    ch_items[0].get("statistics", {}).get("subscriberCount", 0)
                )

        # ── Thumbnail ─────────────────────────────────────────────────────────
        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = (
            thumbnails.get("maxres", {}).get("url")
            or thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
            or ""
        )

        # ── Hashtags / tags ────────────────────────────────────────────────────
        tags = snippet.get("tags") or []
        # Also extract #hashtags from the description
        description = snippet.get("description", "")
        desc_tags = re.findall(r"#(\w+)", description)
        all_tags = list(dict.fromkeys(
            [f"#{t}" for t in tags[:10]] + [f"#{t}" for t in desc_tags[:10]]
        ))[:15]

        logger.info(
            "Fetched YouTube metadata for %s: %dK views, %dK likes",
            video_id,
            views // 1000,
            likes // 1000,
        )

        return {
            "platform": "youtube",
            "url": url,
            "title": snippet.get("title", "Untitled"),
            "creator": snippet.get("channelTitle", "Unknown"),
            "follower_count": follower_count,
            "thumbnail_url": thumbnail_url,
            "views": views,
            "likes": likes,
            "comments": comments,
            "upload_date": upload_date,
            "duration": parse_iso8601_duration(content.get("duration", "")),
            "hashtags": all_tags,
        }

    except HttpError as exc:
        status = exc.resp.status
        if status == 403:
            raise QuotaExceededError("YouTube Data API v3")
        if status == 404:
            raise VideoFetchError(f"YouTube video '{video_id}' not found.")
        raise VideoFetchError(f"YouTube API error {status}: {exc}")
    except (VideoFetchError, QuotaExceededError):
        raise
    except Exception as exc:
        logger.error("Unexpected error fetching YouTube metadata: %s", exc)
        raise VideoFetchError(f"Failed to fetch YouTube metadata: {exc}")
