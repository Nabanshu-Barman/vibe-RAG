import { Citation, VideoMetadata } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type BackendCitation = {
  video_id: 'A' | 'B';
  chunk_label: string;
  chunk_index: number;
};

type BackendEvent =
  | { type: 'token'; content: string }
  | { type: 'citations'; citations: BackendCitation[] }
  | { type: 'done' }
  | { type: 'error'; content: string };

type ChatHistoryItem = { role: string; content: string };

function mapCitations(citations: BackendCitation[]): Citation[] {
  return citations.map((c) => ({
    videoId: c.video_id,
    chunkLabel: c.chunk_label,
    chunkIndex: c.chunk_index,
  }));
}

function toBackendVideo(v: VideoMetadata) {
  return {
    id: v.id,
    platform: v.platform,
    url: v.url,
    title: v.title,
    creator: v.creator,
    follower_count: v.followerCount,
    thumbnail_url: v.thumbnailUrl,
    views: v.views,
    likes: v.likes,
    comments: v.comments,
    upload_date: v.uploadDate,
    duration: v.duration,
    hashtags: v.hashtags,
    engagement_rate: v.engagementRate,
    hook_transcript: v.hookTranscript,
    transcript: v.transcript,
  };
}

export async function* sendChatMessage(
  message: string,
  history: ChatHistoryItem[],
  sessionId: string,
  videoA: VideoMetadata,
  videoB: VideoMetadata
): AsyncGenerator<{ token?: string; citations?: Citation[]; done?: boolean }> {
  if (!sessionId) {
    throw new Error('Missing session. Analyze videos first.');
  }

  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      video_a: toBackendVideo(videoA),
      video_b: toBackendVideo(videoB),
      history,
    }),
  });

  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}));
    const message = err?.detail || err?.message || `Chat failed (${res.status})`;
    throw new Error(message);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let splitIndex = buffer.indexOf('\n\n');
    while (splitIndex !== -1) {
      const rawEvent = buffer.slice(0, splitIndex).trim();
      buffer = buffer.slice(splitIndex + 2);

      if (rawEvent.startsWith('data: ')) {
        const payload = rawEvent.slice(6);
        const event = JSON.parse(payload) as BackendEvent;

        if (event.type === 'token') {
          yield { token: event.content };
        } else if (event.type === 'citations') {
          yield { citations: mapCitations(event.citations), done: true };
        } else if (event.type === 'done') {
          yield { done: true };
        } else if (event.type === 'error') {
          throw new Error(event.content || 'Streaming error');
        }
      }

      splitIndex = buffer.indexOf('\n\n');
    }
  }
}
