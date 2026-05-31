'use client';

import { useState } from 'react';
import styles from './AnalysisPanel.module.css';
import { VideoMetadata } from '@/types';
import EngagementComparison from './EngagementComparison';
import MetricComparisonTable from './MetricComparisonTable';
import HookComparison from './HookComparison';

interface AnalysisPanelProps {
  videoA: VideoMetadata;
  videoB: VideoMetadata;
}

export default function AnalysisPanel({ videoA, videoB }: AnalysisPanelProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className={styles.wrapper}>
      <button
        className={styles.toggle}
        onClick={() => setOpen((p) => !p)}
        aria-expanded={open}
        id="toggle-analysis"
      >
        <span className={styles.toggleIcon}>📊</span>
        <span className={styles.toggleText}>Engagement Analysis</span>
        <span className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`}>▼</span>
      </button>

      <div className={`${styles.content} ${open ? styles.contentOpen : ''}`}>
        <div className={styles.inner}>
          <EngagementComparison videoA={videoA} videoB={videoB} />
          <MetricComparisonTable videoA={videoA} videoB={videoB} />
          <HookComparison videoA={videoA} videoB={videoB} />
        </div>
      </div>
    </div>
  );
}
