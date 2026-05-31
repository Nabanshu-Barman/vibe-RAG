import styles from './HookComparison.module.css';
import { VideoMetadata } from '@/types';

interface HookComparisonProps {
  videoA: VideoMetadata;
  videoB: VideoMetadata;
}

export default function HookComparison({ videoA, videoB }: HookComparisonProps) {
  return (
    <div className={styles.wrapper}>
      <h3 className={styles.title}>Hook Comparison — First 5 Seconds</h3>
      <div className={styles.grid}>
        <div className={`${styles.hookBox} ${styles.hookA}`}>
          <div className={styles.hookLabel}>
            <span className={`${styles.hookBadge} ${styles.hookBadgeVideoA}`}>Video A</span>
            <span className={styles.hookPlatform}>▶ YouTube</span>
          </div>
          <p className={styles.hookText}>"{videoA.hookTranscript}"</p>
        </div>
        <div className={`${styles.hookBox} ${styles.hookB}`}>
          <div className={styles.hookLabel}>
            <span className={`${styles.hookBadge} ${styles.hookBadgeVideoB}`}>Video B</span>
            <span className={styles.hookPlatform}>◉ Instagram</span>
          </div>
          <p className={styles.hookText}>"{videoB.hookTranscript}"</p>
        </div>
      </div>
    </div>
  );
}
