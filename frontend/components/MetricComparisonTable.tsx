import styles from './MetricComparisonTable.module.css';
import { VideoMetadata } from '@/types';

interface MetricComparisonTableProps {
  videoA: VideoMetadata;
  videoB: VideoMetadata;
}

function formatNum(n: number | null): string {
  if (n === null) return 'N/A';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

const METRICS = [
  {
    label: 'Views',
    getVal: (v: VideoMetadata) => v.views,
    format: formatNum,
    higherIsBetter: true,
  },
  {
    label: 'Likes',
    getVal: (v: VideoMetadata) => v.likes,
    format: formatNum,
    higherIsBetter: true,
  },
  {
    label: 'Comments',
    getVal: (v: VideoMetadata) => v.comments,
    format: formatNum,
    higherIsBetter: true,
  },
  {
    label: 'Engagement',
    getVal: (v: VideoMetadata) => v.engagementRate,
    format: (n: number | null) => (n === null ? 'N/A' : `${n.toFixed(2)}%`),
    higherIsBetter: true,
  },
  {
    label: 'Followers',
    getVal: (v: VideoMetadata) => v.followerCount,
    format: formatNum,
    higherIsBetter: true,
  },
];

export default function MetricComparisonTable({ videoA, videoB }: MetricComparisonTableProps) {
  return (
    <div className={styles.wrapper}>
      <h3 className={styles.title}>Metric Breakdown</h3>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>Metric</th>
            <th className={styles.th}>Video A</th>
            <th className={styles.th}>Video B</th>
            <th className={styles.th}>Δ</th>
          </tr>
        </thead>
        <tbody>
          {METRICS.map((metric) => {
            const a = metric.getVal(videoA);
            const b = metric.getVal(videoB);
            const canCompare = a !== null && b !== null;
            const diff = canCompare ? a - b : 0;
            const aWins = canCompare && diff > 0;
            const equal = canCompare && diff === 0;

            return (
              <tr key={metric.label} className={styles.row}>
                <td className={styles.metricLabel}>{metric.label}</td>
                <td className={`${styles.td} ${aWins ? styles.winner : ''}`}>
                  {metric.format(a)}
                </td>
                <td className={`${styles.td} ${!aWins && !equal ? styles.winner : ''}`}>
                  {metric.format(b)}
                </td>
                <td className={styles.td}>
                  {!canCompare || equal ? (
                    <span className={styles.deltaEqual}>—</span>
                  ) : (
                    <span className={`${styles.delta} ${aWins ? styles.deltaUp : styles.deltaDown}`}>
                      {aWins ? '↑' : '↓'} A
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
