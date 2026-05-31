"""
phase5_test.py — Phase 5 smoke test (API wiring + integration readiness)

Tests the HTTP layer using FastAPI's TestClient (no server needed).
Validates: route registration, URL validation, response shapes, error codes.

For the full end-to-end test (real videos, real Gemini), see the curl
commands printed at the end of this script.

Run:
    conda activate viberag2
    python phase5_test.py
"""
import os
import sys
import json

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)

SEP = "─" * 55

def passed(label: str) -> None:
    print(f"  ✓  {label}")

def failed(label: str, detail: str) -> None:
    print(f"  ✗  {label}: {detail}")
    raise AssertionError(label)


def main():
    print("\n" + "=" * 55)
    print("Phase 5 Test — API Wiring & Integration Readiness")
    print("=" * 55 + "\n")

    # ── 1. Health check ───────────────────────────────────────────────────────
    print(SEP)
    print("Step 1 — GET /health")
    r = client.get("/health")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    body = r.json()
    assert body["status"] == "ok",       f"status != ok: {body}"
    assert body["version"] == "1.0.0",   f"version missing: {body}"
    passed("GET /health → 200 {status: ok, version: 1.0.0}")

    # ── 2. Root endpoint ──────────────────────────────────────────────────────
    print(SEP)
    print("Step 2 — GET /")
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "VibeRAG" in body.get("message", ""), f"Unexpected root: {body}"
    assert "/docs" in body.get("docs", ""),       f"docs key missing: {body}"
    passed("GET / → 200 with message + docs link")

    # ── 3. OpenAPI schema ─────────────────────────────────────────────────────
    print(SEP)
    print("Step 3 — GET /openapi.json (route registration check)")
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    paths = schema.get("paths", {})

    required_routes = [
        ("POST",   "/api/analyze"),
        ("POST",   "/api/chat"),
        ("DELETE", "/api/session/{session_id}"),
        ("GET",    "/health"),
    ]
    for method, path in required_routes:
        assert path in paths, f"Route {path} not registered"
        assert method.lower() in paths[path], f"Method {method} missing from {path}"
        passed(f"{method} {path} registered in OpenAPI schema")

    # ── 4. URL validation — YouTube ───────────────────────────────────────────
    print(SEP)
    print("Step 4 — POST /api/analyze URL validation (YouTube)")
    bad_yt_cases = [
        ("not-a-url",         "not a YouTube URL"),
        ("https://vimeo.com/123", "wrong platform"),
        ("",                  "empty string"),
    ]
    for bad_url, reason in bad_yt_cases:
        r = client.post("/api/analyze", json={
            "youtube_url":   bad_url,
            "instagram_url": "https://www.instagram.com/reels/DXTk0zjDNhf/",
        })
        assert r.status_code == 422, \
            f"Expected 422 for '{reason}', got {r.status_code}: {r.text[:200]}"
        passed(f"Invalid YouTube URL ({reason}) → 422")

    # ── 5. URL validation — Instagram ─────────────────────────────────────────
    print(SEP)
    print("Step 5 — POST /api/analyze URL validation (Instagram)")
    bad_ig_cases = [
        ("https://twitter.com/x", "wrong platform"),
        ("https://instagram.com/",   "no reel/post path"),
        ("not-a-url",                "not a URL"),
    ]
    for bad_url, reason in bad_ig_cases:
        r = client.post("/api/analyze", json={
            "youtube_url":   "https://www.youtube.com/watch?v=2eFSU7TFOnk",
            "instagram_url": bad_url,
        })
        assert r.status_code == 422, \
            f"Expected 422 for '{reason}', got {r.status_code}: {r.text[:200]}"
        passed(f"Invalid Instagram URL ({reason}) → 422")

    # ── 6. Chat endpoint validation ───────────────────────────────────────────
    print(SEP)
    print("Step 6 — POST /api/chat input validation")

    # Missing required fields
    r = client.post("/api/chat", json={})
    assert r.status_code == 422, f"Expected 422 for empty body, got {r.status_code}"
    passed("Empty chat body → 422")

    # Missing video_a / video_b
    r = client.post("/api/chat", json={"session_id": "abc", "message": "hi"})
    assert r.status_code == 422, f"Expected 422 for missing videos, got {r.status_code}"
    passed("Chat with missing video_a/video_b → 422")

    # ── 7. Delete session — unknown ID (safe no-op) ───────────────────────────
    print(SEP)
    print("Step 7 — DELETE /api/session/{id} (non-existent session)")
    r = client.delete("/api/session/nonexistent_session_abc123")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "session_id" in body
    assert "deleted"    in body
    assert "message"    in body
    passed("DELETE /api/session/nonexistent → 200 (safe no-op)")

    # ── 8. Response shape — AnalyzeResponse contract ──────────────────────────
    print(SEP)
    print("Step 8 — AnalyzeResponse schema matches frontend contract")
    # Check via OpenAPI schema that all required fields are declared
    schema = client.get("/openapi.json").json()
    schemas = schema.get("components", {}).get("schemas", {})

    video_meta_props = set(schemas.get("VideoMetadata", {}).get("properties", {}).keys())
    required_frontend_fields = {
        "id", "platform", "url", "title", "creator",
        "follower_count", "thumbnail_url", "views", "likes", "comments",
        "upload_date", "duration", "hashtags", "engagement_rate",
        "hook_transcript", "transcript",
    }
    missing = required_frontend_fields - video_meta_props
    assert not missing, f"VideoMetadata missing fields for frontend: {missing}"
    passed(f"VideoMetadata has all {len(required_frontend_fields)} frontend-required fields")

    analyze_props = set(schemas.get("AnalyzeResponse", {}).get("properties", {}).keys())
    assert "video_a"    in analyze_props, "AnalyzeResponse missing video_a"
    assert "video_b"    in analyze_props, "AnalyzeResponse missing video_b"
    assert "session_id" in analyze_props, "AnalyzeResponse missing session_id"
    passed("AnalyzeResponse shape: {video_a, video_b, session_id}  ✓")

    # ── 9. CORS headers ───────────────────────────────────────────────────────
    print(SEP)
    print("Step 9 — CORS preflight headers")
    r = client.options(
        "/api/analyze",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    # TestClient may not fully simulate CORS but checks headers don't error
    assert r.status_code in (200, 204, 400), \
        f"Unexpected CORS preflight status: {r.status_code}"
    passed("OPTIONS /api/analyze → no 5xx error")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("Phase 5 complete — All API wiring tests PASSED")
    print("=" * 55)

    _print_e2e_commands()


def _print_e2e_commands():
    """Print manual end-to-end test commands for the user."""
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 MANUAL END-TO-END TEST COMMANDS (run with uvicorn active)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Start server:
   uvicorn main:app --reload --port 8000

 Step 1 — Analyze (takes ~30-50s):
   curl -s -X POST http://localhost:8000/api/analyze \\
     -H "Content-Type: application/json" \\
     -d '{"youtube_url":"https://www.youtube.com/watch?v=2eFSU7TFOnk","instagram_url":"https://www.instagram.com/reels/DXTk0zjDNhf/"}' \\
     | python -m json.tool

 Step 2 — Chat (replace SESSION_ID with value from Step 1):
   curl -N -s -X POST http://localhost:8000/api/chat \\
     -H "Content-Type: application/json" \\
     -d '{"session_id":"SESSION_ID","message":"Which video has a better hook and why?","video_a":{...},"video_b":{...}}'

 Step 3 — Delete session:
   curl -X DELETE http://localhost:8000/api/session/SESSION_ID

 OpenAPI docs:
   http://localhost:8000/docs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


if __name__ == "__main__":
    main()
