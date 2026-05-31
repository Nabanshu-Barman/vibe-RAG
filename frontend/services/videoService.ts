import { VideoMetadata } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type AnalyzeResponse = {
  video_a: BackendVideoMetadata;
  video_b: BackendVideoMetadata;
  session_id: string;
};

type BackendVideoMetadata = {
  id: 'A' | 'B';
  platform: 'youtube' | 'instagram';
  url: string;
  title: string;
  creator: string;
  follower_count: number | null;
  thumbnail_url: string;
  views: number | null;
  likes: number;
  comments: number;
  upload_date: string;
  duration: string;
  hashtags: string[];
  engagement_rate: number | null;
  hook_transcript: string;
  transcript: string;
};

function mapVideo(v: BackendVideoMetadata): VideoMetadata {
  return {
    id: v.id,
    platform: v.platform,
    url: v.url,
    title: v.title,
    creator: v.creator,
    followerCount: v.follower_count ?? null,
    thumbnailUrl: v.thumbnail_url,
    views: v.views ?? null,
    likes: v.likes,
    comments: v.comments,
    uploadDate: v.upload_date,
    duration: v.duration,
    hashtags: v.hashtags || [],
    engagementRate: v.engagement_rate ?? null,
    hookTranscript: v.hook_transcript,
    transcript: v.transcript,
  };
}

export async function analyzeVideos(
  urlA: string,
  urlB: string
): Promise<{ videoA: VideoMetadata; videoB: VideoMetadata; sessionId: string }> {
  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url_a: urlA, url_b: urlB }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const message = err?.detail || err?.message || `Analyze failed (${res.status})`;
    throw new Error(message);
  }

  const data = (await res.json()) as AnalyzeResponse;
  return {
    videoA: mapVideo(data.video_a),
    videoB: mapVideo(data.video_b),
    sessionId: data.session_id,
  };
}

export async function deleteSession(sessionId: string): Promise<void> {
  if (!sessionId) return;
  await fetch(`${API_BASE}/api/session/${sessionId}`, { method: 'DELETE' });
}
