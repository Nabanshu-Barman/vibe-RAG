"""
services/metadata/instagram_meta.py
--------------------------------------
Fetches Instagram Reel metadata using yt-dlp (info extraction only, no download).

Why switched from instaloader → yt-dlp:
  instaloader queries Instagram's private GraphQL endpoint which returns 401
  Unauthorized on IPs that haven't logged in recently. yt-dlp uses a different
  extraction path (Instagram's oEmbed + page scrape) that is more robust and
  doesn't require authentication for public reels.

  yt-dlp is already a dependency for audio download — no new package needed.

Fields extracted from yt-dlp info dict:
  uploader_id       → creator (@username, stripped of @)
  channel_follower_count → follower_count
  view_count        → views
  like_count        → likes
  comment_count     → comments
  upload_date       → YYYYMMDD → YYYY-MM-DD
  duration          → seconds → mm:ss
  thumbnail         → thumbnail_url
  tags              → hashtags (yt-dlp returns them without #)
  description       → title (first line of caption)
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import json

import yt_dlp

from core.exceptions import VideoFetchError, PrivateAccountError

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_shortcode(url: str) -> str:
    """
    Extract shortcode from an Instagram reel or post URL.
    Instagram uses both /reel/ and /reels/ (plural) depending on client.
      https://www.instagram.com/reel/ABC123XYZ/   → ABC123XYZ
      https://www.instagram.com/reels/ABC123XYZ/  → ABC123XYZ
      https://www.instagram.com/p/ABC123XYZ/      → ABC123XYZ
    """
    match = re.search(r"instagram\.com/(?:reels?|p)/([A-Za-z0-9_-]+)", url)
    if not match:
        raise VideoFetchError(f"Could not extract shortcode from Instagram URL: {url}")
    return match.group(1)


def _format_duration(seconds: float | int | None) -> str:
    """Convert duration in seconds to mm:ss string. Returns '0:00' if None."""
    if not seconds:
        return "0:00"
    total = int(seconds)
    minutes = total // 60
    secs = total % 60
    return f"{minutes}:{secs:02d}"


def _parse_upload_date(raw: str | None) -> str:
    """
    Convert yt-dlp upload_date (YYYYMMDD) to YYYY-MM-DD.
    Returns empty string if parsing fails.
    """
    if not raw or len(raw) != 8:
        return raw or ""
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


# ── Core fetch ────────────────────────────────────────────────────────────────

async def fetch_metadata(url: str) -> dict:
    """
    Fetch Instagram Reel metadata asynchronously via yt-dlp.
    yt-dlp is synchronous — runs in a thread executor.
    """
    return await asyncio.to_thread(_fetch_metadata_sync, url)


def _fetch_metadata_sync(url: str) -> dict:
    """
    Use yt-dlp extract_info(download=False) to pull all reel metadata
    without downloading any media file.
    """
    ffmpeg_exe = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    ffmpeg_dir = os.path.dirname(ffmpeg_exe) if ffmpeg_exe else None

    ydl_opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
    }
    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc).lower()
        if "private" in msg or "login" in msg or "not available" in msg:
            raise PrivateAccountError()
        logger.error("yt-dlp metadata extraction failed for %s: %s", url, exc)
        raise VideoFetchError(f"Could not fetch Instagram Reel metadata: {exc}")
    except Exception as exc:
        logger.error("Unexpected error fetching Instagram metadata: %s", exc)
        raise VideoFetchError(f"Failed to fetch Instagram metadata: {exc}")

    if not info:
        raise VideoFetchError("yt-dlp returned no info for the Instagram URL.")

    # ── Creator ───────────────────────────────────────────────────────────────
    # Prefer the textual uploader (username) over uploader_id (which can be numeric)
    creator = (info.get("uploader") or info.get("uploader_id") or "unknown").lstrip("@")

    # ── Title: first non-empty line of caption / description ──────────────────
    description = info.get("description") or info.get("title") or ""
    first_line = description.split("\n")[0].strip() if description else ""
    title = first_line[:120] or f"Instagram Reel by @{creator}"

    # ── Hashtags: yt-dlp returns them without # ───────────────────────────────
    tags = info.get("tags") or []
    # Also extract #tags from description if tags list is empty
    if not tags and description:
        tags = re.findall(r"#(\w+)", description)
    hashtags = [f"#{tag}" for tag in tags[:15]]

    # ── View count ────────────────────────────────────────────────────────────
    # Use view_count when available. Keep as None when missing so callers can
    # display 'N/A' instead of misleadingly showing 0.
    views = info.get("view_count")

    # ── Stats ─────────────────────────────────────────────────────────────────
    likes    = info.get("like_count") or 0
    comments = info.get("comment_count") or 0

    upload_date    = _parse_upload_date(info.get("upload_date"))
    duration_str   = _format_duration(info.get("duration"))
    thumbnail_url  = info.get("thumbnail") or ""
    # Keep raw follower count (may be None if yt-dlp doesn't expose it)
    follower_count = info.get("channel_follower_count")

    logger.info(
        "[Instagram] Metadata fetched for %s: %s views, %d likes, %d comments",
        creator, (views if views is not None else "N/A"), likes, comments,
    )

    return {
        "platform": "instagram",
        "url": url,
        "title": title,
        "creator": creator,
        # Return raw follower_count (may be None); caller should handle presentation
        "follower_count": follower_count,
        "thumbnail_url": thumbnail_url,
        "views": views,
        "likes": likes,
        "comments": comments,
        "upload_date": upload_date,
        "duration": duration_str,
        "hashtags": hashtags,
    }
