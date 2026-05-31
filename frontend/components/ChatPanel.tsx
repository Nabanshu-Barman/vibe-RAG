'use client';

import { useRef, useEffect } from 'react';
import styles from './ChatPanel.module.css';
import { ChatMessage } from '@/types';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';

const SUGGESTIONS = [
  'Why did Video A get more engagement than Video B?',
  "What's the engagement rate of each?",
  'Compare the hooks in the first 5 seconds',
  'Who created Video B and what\'s their follower count?',
  'Suggest improvements for B based on what worked in A',
];

interface ChatPanelProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  isReady: boolean;
  turnCount: number;
  onSend: (message: string) => void;
  onClear: () => void;
  onCitationClick: (videoId: 'A' | 'B') => void;
}

export default function ChatPanel({
  messages,
  isStreaming,
  isReady,
  turnCount,
  onSend,
  onClear,
  onCitationClick,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const isEmpty = messages.length === 0;

  return (
    <div className={styles.panel}>
      {/* ─── Header ─────────────────────────────────────────── */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.headerIcon}>◈</span>
          <div>
            <h2 className={styles.headerTitle}>AI Chat</h2>
            <p className={styles.headerSub}>Powered by RAG</p>
          </div>
        </div>
        <div className={styles.headerRight}>
          {turnCount > 0 && (
            <span className={styles.memoryPill}>
              🧠 {turnCount} {turnCount === 1 ? 'turn' : 'turns'}
            </span>
          )}
          {messages.length > 0 && (
            <button
              className={styles.clearBtn}
              onClick={onClear}
              title="Clear chat"
              aria-label="Clear chat history"
            >
              ↺
            </button>
          )}
        </div>
      </div>

      {/* ─── Messages ───────────────────────────────────────── */}
      <div className={styles.messages}>
        {isEmpty ? (
          <div className={styles.emptyState}>
            {!isReady ? (
              <>
                <div className={styles.emptyIcon}>◈</div>
                <p className={styles.emptyTitle}>Analyze videos to start chatting</p>
                <p className={styles.emptySub}>
                  Paste your YouTube and Instagram Reel URLs above, then chat with the AI about both videos.
                </p>
              </>
            ) : (
              <>
                <div className={styles.emptyIcon}>💬</div>
                <p className={styles.emptyTitle}>Videos ready — ask anything</p>
                <p className={styles.emptySub}>Try one of these to get started:</p>
                <div className={styles.suggestions}>
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      className={styles.suggestionChip}
                      onClick={() => onSend(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        ) : (
          <div className={styles.messageList}>
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                onCitationClick={onCitationClick}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* ─── Input ──────────────────────────────────────────── */}
      <ChatInput
        onSend={onSend}
        isDisabled={!isReady}
        isStreaming={isStreaming}
        disabledReason={!isReady ? 'Analyze videos first to enable chat' : undefined}
      />
    </div>
  );
}
