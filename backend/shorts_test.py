"""Quick Shorts smoke test."""
import sys, os
sys.path.insert(0, r'C:\Users\naban\Downloads\job\backend')
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

from api.schemas import AnalyzeRequest
from services.transcript.youtube import extract_video_id

SEP = "─" * 45

print(SEP)
print("YouTube Shorts support — extraction check")
cases = [
    ("https://www.youtube.com/shorts/Q0BOH_s9gSU", "Q0BOH_s9gSU"),
    ("https://www.youtube.com/shorts/v84wm8SZQvc", "v84wm8SZQvc"),
    ("https://www.youtube.com/watch?v=2eFSU7TFOnk", "2eFSU7TFOnk"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
]
for url, expected in cases:
    got = extract_video_id(url)
    status = "OK" if got == expected else "FAIL got=" + got
    print(f"  {url[-35:]!r:40s} -> {got!r}  {status}")

print()
print(SEP)
print("Schema validation — Shorts URLs")
schema_cases = [
    ("Shorts+Shorts",
     "https://www.youtube.com/shorts/Q0BOH_s9gSU",
     "https://www.youtube.com/shorts/v84wm8SZQvc"),
    ("Shorts+Watch",
     "https://www.youtube.com/shorts/Q0BOH_s9gSU",
     "https://www.youtube.com/watch?v=2eFSU7TFOnk"),
    ("Shorts+IG",
     "https://www.youtube.com/shorts/Q0BOH_s9gSU",
     "https://www.instagram.com/reels/DXTk0zjDNhf/"),
    ("Watch+Shorts",
     "https://www.youtube.com/watch?v=2eFSU7TFOnk",
     "https://www.youtube.com/shorts/Q0BOH_s9gSU"),
]
for label, a, b in schema_cases:
    try:
        r = AnalyzeRequest(url_a=a, url_b=b)
        print(f"  {label}: OK")
    except Exception as e:
        print(f"  {label}: FAIL  {e}")

print()
print("All checks passed")
