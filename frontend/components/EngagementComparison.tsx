import styles from './EngagementComparison.module.css';
import { VideoMetadata } from '@/types';

interface EngagementComparisonProps {
  videoA: VideoMetadata;
  videoB: VideoMetadata;
}

export default function EngagementComparison({ videoA, videoB }: EngagementComparisonProps) {
  const rateA = videoA.engagementRate;
  const rateB = videoB.engagementRate;
  const canCompare = rateA !== null && rateB !== null;
  const maxRate = canCompare ? Math.max(rateA, rateB, 1) : 1;
  const widthA = canCompare ? (rateA / maxRate) * 100 : 0;
  const widthB = canCompare ? (rateB / maxRate) * 100 : 0;
  const winner = canCompare && rateA >= rateB ? 'A' : 'B';
  const diff = canCompare ? Math.abs(rateA - rateB).toFixed(2) : '0.00';

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <h3 className={styles.title}>Engagement Rate</h3>
        <span className={styles.winnerBadge}>
          {canCompare ? `🏆 Video ${winner} leads by ${diff}%` : 'Engagement rate unavailable'}
        </span>
      </div>

      <div className={styles.bars}>
        <div className={styles.barRow}>
          <span className={styles.barLabel}>Video A</span>
          <div className={styles.barTrack}>
            <div
              className={`${styles.bar} ${styles.barA}`}
              style={{ width: `${widthA}%` }}
            />
          </div>
          <span className={styles.barValue}>
            {rateA === null ? 'N/A' : `${rateA.toFixed(2)}%`}
          </span>
        </div>

        <div className={styles.barRow}>
          <span className={styles.barLabel}>Video B</span>
          <div className={styles.barTrack}>
            <div
              className={`${styles.bar} ${styles.barB}`}
              style={{ width: `${widthB}%` }}
            />
          </div>
          <span className={styles.barValue}>
            {rateB === null ? 'N/A' : `${rateB.toFixed(2)}%`}
          </span>
        </div>
      </div>
    </div>
  );
}
