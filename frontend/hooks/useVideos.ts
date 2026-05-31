'use client';

import { useState, useCallback } from 'react';
import { VideoMetadata, AppStatus } from '@/types';
import { analyzeVideos, deleteSession } from '@/services/videoService';

export function useVideos() {
  const [videoA, setVideoA] = useState<VideoMetadata | null>(null);
  const [videoB, setVideoB] = useState<VideoMetadata | null>(null);
  const [status, setStatus] = useState<AppStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [highlightedVideo, setHighlightedVideo] = useState<'A' | 'B' | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const analyze = useCallback(async (urlA: string, urlB: string) => {
    setStatus('analyzing');
    setError(null);

    try {
      const { videoA: a, videoB: b, sessionId: newSessionId } = await analyzeVideos(
        urlA,
        urlB
      );
      setVideoA(a);
      setVideoB(b);
      setSessionId(newSessionId);
      setStatus('ready');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to analyze videos');
      setStatus('error');
    }
  }, []);

  const highlightVideo = useCallback((id: 'A' | 'B') => {
    setHighlightedVideo(id);
    setTimeout(() => setHighlightedVideo(null), 1500);
  }, []);

  const reset = useCallback(() => {
    if (sessionId) {
      deleteSession(sessionId).catch(() => undefined);
    }
    setVideoA(null);
    setVideoB(null);
    setStatus('idle');
    setError(null);
    setSessionId(null);
  }, [sessionId]);

  return {
    videoA,
    videoB,
    status,
    error,
    highlightedVideo,
    sessionId,
    analyze,
    highlightVideo,
    reset,
  };
}
