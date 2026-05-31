export interface VideoMetadata {
  id: 'A' | 'B';
  platform: 'youtube' | 'instagram';
  url: string;
  title: string;
  creator: string;
  creatorAvatar?: string;
  followerCount: number | null;
  thumbnailUrl: string;
  views: number | null;
  likes: number;
  comments: number;
  uploadDate: string;
  duration: string; // e.g. "5:32"
  hashtags: string[];
  engagementRate: number | null; // percentage
  hookTranscript: string; // first ~5 seconds of transcript
  transcript: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: Citation[];
  isStreaming?: boolean;
}

export interface Citation {
  videoId: 'A' | 'B';
  chunkLabel: string; // e.g. "Intro", "Chunk 3"
  chunkIndex: number;
}

export type AppStatus = 'idle' | 'analyzing' | 'ready' | 'chatting' | 'error';
