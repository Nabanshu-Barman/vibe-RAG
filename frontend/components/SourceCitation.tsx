import styles from './SourceCitation.module.css';
import { Citation } from '@/types';

interface SourceCitationProps {
  citations: Citation[];
  onCitationClick: (videoId: 'A' | 'B') => void;
}

export default function SourceCitation({ citations, onCitationClick }: SourceCitationProps) {
  if (!citations.length) return null;

  return (
    <div className={styles.wrapper}>
      <span className={styles.label}>Sources</span>
      <div className={styles.chips}>
        {citations.map((c, i) => (
          <button
            key={i}
            className={`${styles.chip} ${styles[`video${c.videoId}`]}`}
            onClick={() => onCitationClick(c.videoId)}
            title={`Jump to Video ${c.videoId}`}
          >
            <span className={styles.chipIcon}>◈</span>
            Video {c.videoId}
            {c.chunkLabel && <span className={styles.chunkLabel}>— {c.chunkLabel}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
