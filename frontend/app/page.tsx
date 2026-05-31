'use client';

import { useCallback } from 'react';
import styles from './page.module.css';
import AppBar from '@/components/AppBar';
import URLInputSection from '@/components/URLInputSection';
import VideoCard from '@/components/VideoCard';
import VideoCardSkeleton from '@/components/VideoCardSkeleton';
import ChatPanel from '@/components/ChatPanel';
import AnalysisPanel from '@/components/AnalysisPanel';
import Toast from '@/components/Toast';
import { useVideos } from '@/hooks/useVideos';
import { useChat } from '@/hooks/useChat';

export default function HomePage() {
  const {
    videoA,
    videoB,
    status,
    error,
    highlightedVideo,
    sessionId,
    analyze,
    highlightVideo,
    reset,
  } = useVideos();
  const { messages, isStreaming, sendMessage, clearChat } = useChat();

  const handleAnalyze = useCallback(
    (urlA: string, urlB: string) => {
      clearChat();
      analyze(urlA, urlB);
    },
    [analyze, clearChat]
  );

  const handleSend = useCallback(
    (msg: string) => {
      sendMessage(msg, sessionId, videoA, videoB);
    },
    [sendMessage, sessionId, videoA, videoB]
  );

  const handleCitationClick = useCallback(
    (videoId: 'A' | 'B') => {
      highlightVideo(videoId);
      // Scroll to video cards
      document.getElementById(`video-card-${videoId}`)?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    },
    [highlightVideo]
  );

  const isReady = status === 'ready';
  const isAnalyzing = status === 'analyzing';
  const turnCount = Math.floor(messages.filter((m) => m.role === 'user').length);

  return (
    <>
      <AppBar status={isStreaming ? 'chatting' : status} />

      {error && (
        <Toast
          message={error}
          type="error"
          onDismiss={reset}
        />
      )}

      <main className={styles.main}>
        {/* ─── Left Panel ─────────────────────────────── */}
        <section className={styles.leftPanel} aria-label="Video Analysis">
          {!isReady && !isAnalyzing ? (
            <URLInputSection onAnalyze={handleAnalyze} isLoading={isAnalyzing} />
          ) : (
            <div className={styles.videoSection}>
              {/* Header row with back button when videos loaded */}
              {isReady && (
                <div className={styles.videosHeader}>
                  <span className={styles.videosTitle}>Comparing 2 Videos</span>
                  <button className={styles.resetBtn} onClick={reset}>
                    ↺ New Analysis
                  </button>
                </div>
              )}

              {/* Video Cards */}
              <div className={styles.cardsGrid}>
                {isAnalyzing ? (
                  <>
                    <VideoCardSkeleton />
                    <VideoCardSkeleton />
                  </>
                ) : (
                  <>
                    {videoA && (
                      <div id="video-card-A">
                        <VideoCard
                          video={videoA}
                          animationDelay={0}
                          isHighlighted={highlightedVideo === 'A'}
                        />
                      </div>
                    )}
                    {videoB && (
                      <div id="video-card-B">
                        <VideoCard
                          video={videoB}
                          animationDelay={150}
                          isHighlighted={highlightedVideo === 'B'}
                        />
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Analysis Panel */}
              {isReady && videoA && videoB && (
                <AnalysisPanel videoA={videoA} videoB={videoB} />
              )}
            </div>
          )}
        </section>

        {/* ─── Right Panel ────────────────────────────── */}
        <aside className={styles.rightPanel} aria-label="AI Chat">
          <ChatPanel
            messages={messages}
            isStreaming={isStreaming}
            isReady={isReady}
            turnCount={turnCount}
            onSend={handleSend}
            onClear={clearChat}
            onCitationClick={handleCitationClick}
          />
        </aside>
      </main>
    </>
  );
}
