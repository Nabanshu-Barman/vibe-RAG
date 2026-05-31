import styles from './VideoCard.module.css';
import { VideoMetadata } from '@/types';

interface VideoCardProps {
  video: VideoMetadata;
  animationDelay?: number;
  isHighlighted?: boolean;
}

function formatNumber(n: number | null): string {
  if (n === null) return 'N/A';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function formatFollowers(n: number | null): string {
  if (n === null) return 'Followers: N/A';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M followers`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K followers`;
  return `${n} followers`;
}

function getEngagementTier(rate: number | null): { label: string; className: string } {
  if (rate === null) return { label: 'N/A', className: 'engLow' };
  if (rate >= 5) return { label: 'High', className: 'engHigh' };
  if (rate >= 2) return { label: 'Average', className: 'engAvg' };
  return { label: 'Low', className: 'engLow' };
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export default function VideoCard({ video, animationDelay = 0, isHighlighted }: VideoCardProps) {
  const tier = getEngagementTier(video.engagementRate);
  const MAX_TAGS = 7;
  const visibleTags = video.hashtags.slice(0, MAX_TAGS);
  const extraTags = video.hashtags.length - MAX_TAGS;
  const engagementDisplay = video.engagementRate === null ? 'N/A' : `${video.engagementRate.toFixed(2)}%`;

  return (
    <div
      className={`${styles.card} ${isHighlighted ? styles.highlighted : ''}`}
      style={{ animationDelay: `${animationDelay}ms` }}
    >
      {/* ─── Card Header ─────────────────────────────── */}
      <div className={styles.cardHeader}>
        <span className={`${styles.platformBadge} ${styles[`platform_${video.platform}`]}`}>
          {video.platform === 'youtube' ? '▶ YouTube' : '◉ Instagram'}
        </span>
        <span className={styles.videoIdBadge}>Video {video.id}</span>
      </div>

      {/* ─── Thumbnail ───────────────────────────────── */}
      <a
        href={video.url}
        target="_blank"
        rel="noopener noreferrer"
        className={styles.thumbnailLink}
        title={`Watch ${video.title}`}
      >
        <div className={styles.thumbnailWrap}>
          <img
            src={video.thumbnailUrl}
            alt={video.title}
            className={styles.thumbnail}
            loading="lazy"
          />
          <div className={styles.thumbnailOverlay}>
            <div className={styles.playBtn}>▶</div>
            <span className={styles.duration}>{video.duration}</span>
          </div>
        </div>
      </a>

      {/* ─── Title ───────────────────────────────────── */}
      <h2 className={styles.title} title={video.title}>
        {video.title}
      </h2>

      {/* ─── Creator Row ─────────────────────────────── */}
      <div className={styles.creatorRow}>
        <div className={styles.avatar}>
          {video.creator.charAt(0).toUpperCase()}
        </div>
        <div className={styles.creatorInfo}>
          <span className={styles.creatorName}>@{video.creator}</span>
          <span className={styles.followers}>{formatFollowers(video.followerCount)}</span>
        </div>
      </div>

      {/* ─── Stats Bar ───────────────────────────────── */}
      <div className={styles.statsBar}>
        <div className={styles.statItem}>
          <span className={styles.statIcon}>👁</span>
          <span className={styles.statValue}>{formatNumber(video.views)}</span>
          <span className={styles.statLabel}>Views</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statIcon}>❤️</span>
          <span className={styles.statValue}>{formatNumber(video.likes)}</span>
          <span className={styles.statLabel}>Likes</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statIcon}>💬</span>
          <span className={styles.statValue}>{formatNumber(video.comments)}</span>
          <span className={styles.statLabel}>Comments</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statIcon}>📅</span>
          <span className={styles.statValue}>{formatDate(video.uploadDate)}</span>
          <span className={styles.statLabel}>Posted</span>
        </div>
      </div>

      {/* ─── Engagement Rate ─────────────────────────── */}
      <div className={styles.engagementRow}>
        <span className={styles.engLabel}>Engagement Rate</span>
        <div className={styles.engValue}>
          <span className={styles.engNumber}>{engagementDisplay}</span>
          <span className={`${styles.engBadge} ${styles[tier.className]}`}>{tier.label}</span>
        </div>
      </div>

      {/* ─── Hashtags ────────────────────────────────── */}
      <div className={styles.hashtags}>
        {visibleTags.map((tag) => (
          <span key={tag} className={styles.hashtagPill}>{tag}</span>
        ))}
        {extraTags > 0 && (
          <span className={styles.moreTagsPill}>+{extraTags} more</span>
        )}
      </div>
    </div>
  );
}
