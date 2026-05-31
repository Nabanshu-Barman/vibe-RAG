"""
services/transcript/instagram.py
----------------------------------
Transcribes Instagram Reels using yt-dlp (audio extraction) + Whisper (local STT).

Why this approach:
  - Instagram has no public caption API
  - yt-dlp downloads only the audio stream (no full video), minimising disk I/O
  - Whisper "tiny" transcribes a 60s reel in ~8-12s on CPU; acceptable latency
  - The model is loaded once at startup and reused across all requests (singleton)

Upgrade path:
  - Swap Whisper for AssemblyAI async API when CPU becomes a bottleneck at scale
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
from functools import lru_cache
from typing import TypedDict

import yt_dlp
import whisper

from core.config import settings
from core.exceptions import TranscriptUnavailableError, VideoFetchError

logger = logging.getLogger(__name__)


class WhisperSegment(TypedDict):
    text: str
    start: float
    end: float


# ── Whisper singleton ─────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_whisper_model() -> whisper.Whisper:
    """
    Load Whisper model exactly once per process lifetime.
    lru_cache(maxsize=1) ensures subsequent calls return the cached model.
    Model size is controlled by WHISPER_MODEL in .env (default: "tiny").
    """
    model_name = settings.whisper_model
    logger.info("Loading Whisper model '%s' — this runs once at startup.", model_name)
    model = whisper.load_model(model_name)
    logger.info("Whisper model '%s' loaded successfully.", model_name)
    return model


# ── Shortcode extraction ──────────────────────────────────────────────────────

def extract_shortcode(url: str) -> str:
    """
    Extract the Instagram shortcode from a reel or post URL.
    Instagram uses both /reel/ and /reels/ (plural) depending on the client.
      https://www.instagram.com/reel/ABC123XYZ/   → ABC123XYZ
      https://www.instagram.com/reels/ABC123XYZ/  → ABC123XYZ
      https://www.instagram.com/p/ABC123XYZ/      → ABC123XYZ
    """
    match = re.search(r"instagram\.com/(?:reels?|p)/([A-Za-z0-9_-]+)", url)
    if not match:
        raise VideoFetchError(f"Could not extract shortcode from Instagram URL: {url}")
    return match.group(1)


# ── Audio download ─────────────────────────────────────────────────────────────

def _download_audio(url: str, output_path: str) -> str:
    """
    Download only the audio stream from an Instagram Reel using yt-dlp.
    Returns the actual output file path.

    ffmpeg detection: we use shutil.which() to find the system ffmpeg and pass
    it explicitly via ffmpeg_location. This is necessary because asyncio.to_thread
    spawns in a thread pool that may not inherit the full shell PATH on Windows.
    If ffmpeg is not found, we skip the WAV postprocessor and let Whisper handle
    the native audio format directly (Whisper supports mp4/webm/m4a).
    """
    import shutil

    ffmpeg_exe = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    ffmpeg_dir = os.path.dirname(ffmpeg_exe) if ffmpeg_exe else None

    if ffmpeg_dir:
        logger.info("ffmpeg found at: %s", ffmpeg_exe)
    else:
        logger.warning(
            "ffmpeg not found via shutil.which — Whisper will handle raw audio format. "
            "Install ffmpeg and add it to PATH for best results."
        )

    ydl_opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
    }

    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    # After postprocessing yt-dlp appends the codec extension
    if ffmpeg_dir:
        wav_path = output_path + ".wav"
        if os.path.exists(wav_path):
            return wav_path

    # Fallback: find any file yt-dlp wrote with our base path
    directory = os.path.dirname(output_path)
    base = os.path.basename(output_path)
    candidates = sorted(
        f for f in os.listdir(directory)
        if f.startswith(base) and not f.endswith(".part")
    )
    if candidates:
        return os.path.join(directory, candidates[0])

    raise VideoFetchError("Could not locate downloaded audio file from yt-dlp.")


def _transcribe_audio(audio_path: str) -> dict:
    """
    Transcribe audio using the preloaded Whisper model.
    Returns Whisper's full output dict: {text, segments, language}.
    """
    model = _get_whisper_model()
    result = model.transcribe(audio_path, fp16=False)  # fp16=False for CPU compatibility
    return result


# ── Public async interface ────────────────────────────────────────────────────

async def fetch_transcript(url: str) -> tuple[str, str, list[WhisperSegment]]:
    """
    Download and transcribe an Instagram Reel.
    Both yt-dlp and Whisper are blocking — run them in a thread executor
    so they don't block the FastAPI event loop.

    Returns:
        full_transcript (str): Full spoken text joined.
        hook_transcript (str): First 5 seconds of speech.
        segments (list): Whisper segments with start/end timestamps.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "reel_audio")

        try:
            # Download audio in thread (blocking I/O)
            logger.info("Downloading Instagram audio from %s", url)
            audio_path = await asyncio.to_thread(_download_audio, url, output_path)
            logger.info("Audio downloaded to %s", audio_path)

            # Transcribe in thread (blocking CPU)
            logger.info("Transcribing with Whisper '%s'...", settings.whisper_model)
            result = await asyncio.to_thread(_transcribe_audio, audio_path)
            logger.info("Transcription complete: %d chars", len(result.get("text", "")))

        except yt_dlp.utils.DownloadError as exc:
            logger.error("yt-dlp download failed: %s", exc)
            raise VideoFetchError(f"Could not download Instagram Reel: {exc}")
        except Exception as exc:
            logger.error("Instagram transcription failed: %s", exc)
            raise TranscriptUnavailableError("Instagram Reel")

        segments: list[WhisperSegment] = result.get("segments", [])
        full_text = result.get("text", "").strip()

        # Hook: spoken words in the first 5 seconds
        hook_parts = [s["text"].strip() for s in segments if s["start"] < 5.0]
        hook_text = " ".join(hook_parts).strip() or full_text[:200]

        return full_text, hook_text, segments
