# combined.py - Phase 2 smoke test
# Run from the backend directory with the viberag env active:
#   conda activate viberag
#   python combined.py
#
# YouTube note: the video must have CC captions enabled on YouTube.
# If you see "Transcript unavailable", replace yt_url with a video that has CC.

import asyncio
import sys
import os
import logging
logging.getLogger().setLevel(logging.WARNING)

# Ensure imports resolve from the backend root when run as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.ingest import fetch_video_data



# ── Test URLs ──────────────────────────────────────────────────────────────────
# Replace with any YouTube video that has captions enabled (CC button active on YouTube)
yt_url = "https://youtube.com/shorts/fsiwrNq192U?si=WRsOXvkjzk7VrEj_"

# Instagram: /reels/ and /reel/ both work now
ig_url = "https://www.instagram.com/reel/DXQOfyTDJ6N/?igsh=MTgxbzRzMXlvZmFpNQ=="


async def main():
    print(f"\n{'='*60}")
    print("VibeRAG — Phase 2 Pipeline Test")
    print(f"{'='*60}")
    print(f"YouTube : {yt_url}")
    print(f"Instagram: {ig_url}")
    print(f"{'='*60}\n")

    try:
        video_a, video_b = await fetch_video_data(yt_url, ig_url)

        print("✅  VIDEO A (YouTube)")
        print(f"   Title       : {video_a.title}")
        follower_display_a = f"{video_a.follower_count:,} subscribers" if video_a.follower_count else "Subscribers: N/A"
        print(f"   Creator     : {video_a.creator}  ({follower_display_a})")
        views_display_a = f"{video_a.views:,}" if video_a.views is not None else "N/A"
        print(f"   Views       : {views_display_a}")
        print(f"   Likes       : {video_a.likes:,}")
        print(f"   Comments    : {video_a.comments:,}")
        print(f"   Engagement  : {f'{video_a.engagement_rate}%' if video_a.engagement_rate is not None else 'N/A'}")
        print(f"   Duration    : {video_a.duration}")
        print(f"   Upload Date : {video_a.upload_date}")
        print(f"   Hashtags    : {', '.join(video_a.hashtags[:5]) or 'none'}")
        print(f"   Hook (0-5s) : {video_a.hook_transcript[:120]!r}")
        print(f"   Transcript  : {video_a.transcript[:200]!r}...")
        print()

        print("✅  VIDEO B (Instagram)")
        print(f"   Title       : {video_b.title}")
        follower_display = f"{video_b.follower_count:,} followers" if video_b.follower_count else "Followers: N/A"
        print(f"   Creator     : @{video_b.creator}  ({follower_display})")
        views_display_b = f"{video_b.views:,}" if video_b.views is not None else "N/A"
        print(f"   Views       : {views_display_b}")
        print(f"   Likes       : {video_b.likes:,}")
        print(f"   Comments    : {video_b.comments:,}")
        print(f"   Engagement  : {f'{video_b.engagement_rate}%' if video_b.engagement_rate is not None else 'N/A'}")
        print(f"   Duration    : {video_b.duration}")
        print(f"   Upload Date : {video_b.upload_date}")
        print(f"   Hashtags    : {', '.join(video_b.hashtags[:5]) or 'none'}")
        print(f"   Hook (0-5s) : {video_b.hook_transcript[:120]!r}")
        print(f"   Transcript  : {video_b.transcript[:200]!r}...")
        print()

        print(f"{'='*60}")
        print("Phase 2 complete — both pipelines working.")
        print(f"{'='*60}\n")

    except Exception as exc:
        print(f"\n❌  ERROR: {exc}", file=sys.stderr)
        print("\nCommon fixes:", file=sys.stderr)
        print("  YouTube 'Transcript unavailable': the video has no CC captions.", file=sys.stderr)
        print("    → Open the video on YouTube and check if CC works.", file=sys.stderr)
        print("    → Try a different YouTube video that has captions.", file=sys.stderr)
        print("  Instagram 'private': the account is private.", file=sys.stderr)
        print("  ffmpeg not found: ensure ffmpeg is on your PATH.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())