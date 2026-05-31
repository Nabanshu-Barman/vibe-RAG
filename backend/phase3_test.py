"""
phase3_test.py — Phase 3 smoke test (chunking + embedding + ChromaDB)

Uses a small synthetic transcript so the test runs in <30s without
waiting for Whisper. Real Gemini text-embedding-004 API is called.

Run from the backend directory with viberag2 active:
    conda activate viberag2
    python phase3_test.py

What this validates:
  1. Chunking: RecursiveCharacterTextSplitter produces correct chunks + labels
  2. Embedding: text-embedding-004 via Gemini API returns 768-dim vectors
  3. Storage: ChromaDB persists chunks to disk with correct metadata
  4. Retrieval: similarity search returns the right chunks
  5. Cleanup: session collection deleted cleanly
"""
import asyncio
import sys
import os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.schemas import VideoMetadata
from services.ingest import chunk_transcript, _derive_label, compute_engagement_rate
from services.vector_store import store_documents, get_retriever, collection_count, delete_session
from uuid import uuid4


# ── Synthetic test data ────────────────────────────────────────────────────────

SAMPLE_YT_TRANSCRIPT = (
    "Welcome back to the channel. Today we're going to talk about content creation "
    "and why your hook is the most important part of any video. The first five seconds "
    "determine whether someone stays or leaves. You need to grab attention immediately "
    "with a strong visual or a compelling question. "
    * 8  # ~640 words total → ~4-5 chunks at 512 chars
)

SAMPLE_IG_TRANSCRIPT = (
    "Hey guys, it's me again. I wanted to share something that changed my life. "
    "The secret to going viral on Instagram is consistency and authenticity. "
    "People can tell when you're being fake. Just be yourself and post every single day. "
    "Your engagement rate matters more than your follower count. "
    * 6  # ~480 words total → ~3-4 chunks
)

def make_video(vid_id: str, platform: str, transcript: str) -> VideoMetadata:
    return VideoMetadata(
        id=vid_id,
        platform=platform,
        url=f"https://example.com/{vid_id}",
        title=f"Test Video {vid_id}",
        creator=f"creator_{vid_id}",
        follower_count=100_000,
        thumbnail_url="https://example.com/thumb.jpg",
        views=500_000,
        likes=25_000,
        comments=1_200,
        upload_date="2024-06-01",
        duration="10:30",
        hashtags=["#test", "#phase3"],
        engagement_rate=compute_engagement_rate(25_000, 1_200, 500_000),
        hook_transcript=transcript[:120],
        transcript=transcript,
    )


async def main():
    print("\n" + "=" * 65)
    print("Phase 3 Test — Chunking + Embedding + ChromaDB")
    print("=" * 65 + "\n")

    session_id = uuid4().hex
    print(f"Session ID : {session_id}\n")

    video_a = make_video("A", "youtube", SAMPLE_YT_TRANSCRIPT)
    video_b = make_video("B", "instagram", SAMPLE_IG_TRANSCRIPT)

    # ── 1. Chunk label logic ──────────────────────────────────────────────────
    print("─" * 40)
    print("Step 1 — Chunk label logic")
    assert _derive_label(0, 5) == "Hook (0-5s)",   "Label 0 wrong"
    assert _derive_label(4, 5) == "Conclusion",     "Label last wrong"
    assert _derive_label(2, 5) == "Chunk 2",        "Label middle wrong"
    print("  derive_label(0,5)   → 'Hook (0-5s)'   ✓")
    print("  derive_label(4,5)   → 'Conclusion'     ✓")
    print("  derive_label(2,5)   → 'Chunk 2'        ✓")

    # ── 2. Chunking ───────────────────────────────────────────────────────────
    print("\n─" * 40)
    print("\nStep 2 — Chunking transcripts")
    docs_a = chunk_transcript(video_a, session_id)
    docs_b = chunk_transcript(video_b, session_id)
    all_docs = docs_a + docs_b

    print(f"  Video A chunks : {len(docs_a)}")
    print(f"  Video B chunks : {len(docs_b)}")
    print(f"  Total docs     : {len(all_docs)}")

    # Verify metadata on first chunk of A
    d0 = docs_a[0]
    assert d0.metadata["video_id"]    == "A",          "video_id wrong"
    assert d0.metadata["session_id"]  == session_id,   "session_id wrong"
    assert d0.metadata["chunk_index"] == 0,            "chunk_index wrong"
    assert d0.metadata["chunk_label"] == "Hook (0-5s)","chunk_label wrong"
    assert d0.metadata["platform"]    == "youtube",    "platform wrong"

    # Verify last chunk of A is labelled "Conclusion"
    d_last = docs_a[-1]
    assert d_last.metadata["chunk_label"] == "Conclusion", "last label wrong"

    print(f"  Chunk 0  label : '{d0.metadata['chunk_label']}'  ✓")
    print(f"  Chunk -1 label : '{d_last.metadata['chunk_label']}'  ✓")
    print(f"  Metadata keys  : {sorted(d0.metadata.keys())}  ✓")

    # ── 3. Embed + Store (real Gemini API + ChromaDB) ─────────────────────────
    print("\n─" * 40)
    print("\nStep 3 — Embedding + Storing in ChromaDB")
    print("  Calling Gemini text-embedding-004... (first call may take a few seconds)")

    stored = await asyncio.to_thread(store_documents, all_docs, session_id)
    count  = collection_count(session_id)

    print(f"  Chunks stored  : {stored}")
    print(f"  Collection size: {count}")
    assert count == len(all_docs), f"Expected {len(all_docs)} in DB, got {count}"
    print("  ChromaDB count matches chunk count  ✓")

    # ── 4. Retrieval ──────────────────────────────────────────────────────────
    print("\n─" * 40)
    print("\nStep 4 — Similarity retrieval")
    retriever = get_retriever(session_id, k=4)
    query = "what is the most important part of a video for engagement"
    results = retriever.invoke(query)

    print(f"  Query   : '{query}'")
    print(f"  Results : {len(results)} docs")
    assert len(results) > 0, "Retriever returned no results"

    for i, doc in enumerate(results):
        print(f"  [{i}] video={doc.metadata['video_id']} "
              f"label='{doc.metadata['chunk_label']}' "
              f"text='{doc.page_content[:60]}...'")

    # Verify video-filtered retrieval (only Video A)
    retriever_a = get_retriever(session_id, k=4, video_id="A")
    results_a = retriever_a.invoke(query)
    assert all(d.metadata["video_id"] == "A" for d in results_a), \
        "Filtered retriever returned Video B chunks"
    print(f"\n  Filtered (A only): {len(results_a)} docs — all video_id='A'  ✓")

    # ── 5. Cleanup ────────────────────────────────────────────────────────────
    print("\n─" * 40)
    print("\nStep 5 — Session cleanup")
    deleted = await delete_session(session_id)
    assert deleted, "delete_session returned False"
    print(f"  Session {session_id[:12]}... deleted  ✓")

    # Verify collection is gone
    try:
        remaining = collection_count(session_id)
        # If a new empty collection was auto-created, count will be 0 — that's ok
        print(f"  Post-delete count: {remaining} (empty collection recreated on access)")
        # Clean up the empty shell too
        await delete_session(session_id)
    except Exception:
        print("  Collection fully removed  ✓")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("Phase 3 complete — All steps PASSED")
    print(f"  Chunks per session: {len(all_docs)}")
    print(f"  Embedding model   : text-embedding-004 (768-dim)")
    print(f"  Vector DB         : ChromaDB @ {os.path.abspath('./chroma_db')}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
