'use client';

import { useRef, useEffect, useCallback } from 'react';
import styles from './ChatInput.module.css';

interface ChatInputProps {
  onSend: (message: string) => void;
  isDisabled: boolean;
  isStreaming: boolean;
  disabledReason?: string;
}

export default function ChatInput({
  onSend,
  isDisabled,
  isStreaming,
  disabledReason,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = () => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
  };

  const handleSend = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    const value = ta.value.trim();
    if (!value || isDisabled || isStreaming) return;
    onSend(value);
    ta.value = '';
    ta.style.height = 'auto';
  }, [onSend, isDisabled, isStreaming]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    if (!isStreaming && !isDisabled) {
      textareaRef.current?.focus();
    }
  }, [isStreaming, isDisabled]);

  return (
    <div className={styles.wrapper}>
      <div className={`${styles.inputRow} ${isDisabled ? styles.inputDisabled : ''}`} title={disabledReason}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          placeholder={isDisabled ? disabledReason || 'Analyze videos first…' : 'Ask anything about the videos…'}
          onInput={adjustHeight}
          onKeyDown={handleKeyDown}
          disabled={isDisabled || isStreaming}
          rows={1}
          id="chat-input"
        />
        <button
          className={`${styles.sendBtn} ${isStreaming ? styles.loading : ''}`}
          onClick={handleSend}
          disabled={isDisabled || isStreaming}
          aria-label="Send message"
          id="send-btn"
        >
          {isStreaming ? (
            <span className={styles.spinner} />
          ) : (
            <span className={styles.sendIcon}>↑</span>
          )}
        </button>
      </div>
      <p className={styles.hint}>
        Press <kbd>Enter</kbd> to send · <kbd>Shift+Enter</kbd> for new line
      </p>
    </div>
  );
}
