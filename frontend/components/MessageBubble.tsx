import styles from './MessageBubble.module.css';
import { ChatMessage } from '@/types';
import SourceCitation from './SourceCitation';

interface MessageBubbleProps {
  message: ChatMessage;
  onCitationClick: (videoId: 'A' | 'B') => void;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function renderContent(content: string): string {
  // Simple markdown-like rendering for bold text
  return content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>');
}

export default function MessageBubble({ message, onCitationClick }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`${styles.wrapper} ${isUser ? styles.userWrapper : styles.assistantWrapper}`}>
      {!isUser && (
        <div className={styles.avatar}>
          <span>◈</span>
        </div>
      )}
      <div className={`${styles.bubble} ${isUser ? styles.userBubble : styles.assistantBubble}`}>
        {isUser ? (
          <p className={styles.content}>{message.content}</p>
        ) : (
          <div
            className={styles.content}
            dangerouslySetInnerHTML={{
              __html: `<p>${renderContent(message.content)}</p>`,
            }}
          />
        )}
        {message.isStreaming && (
          <span className={styles.cursor}>|</span>
        )}
        {!isUser && message.citations && message.citations.length > 0 && !message.isStreaming && (
          <SourceCitation citations={message.citations} onCitationClick={onCitationClick} />
        )}
        <span className={styles.timestamp}>{formatTime(message.timestamp)}</span>
      </div>
    </div>
  );
}
