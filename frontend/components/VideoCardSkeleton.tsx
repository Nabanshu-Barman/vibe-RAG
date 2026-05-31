import styles from './VideoCardSkeleton.module.css';

export default function VideoCardSkeleton() {
  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <div className={`${styles.skel} ${styles.badgeSkel}`} />
        <div className={`${styles.skel} ${styles.idSkel}`} />
      </div>
      <div className={`${styles.skel} ${styles.thumbnailSkel}`} />
      <div className={styles.body}>
        <div className={`${styles.skel} ${styles.titleSkel}`} />
        <div className={`${styles.skel} ${styles.titleSkelShort}`} />
        <div className={styles.creatorRow}>
          <div className={`${styles.skel} ${styles.avatarSkel}`} />
          <div className={styles.creatorLines}>
            <div className={`${styles.skel} ${styles.nameSkel}`} />
            <div className={`${styles.skel} ${styles.followerSkel}`} />
          </div>
        </div>
        <div className={styles.statsBar}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className={styles.statItem}>
              <div className={`${styles.skel} ${styles.statIconSkel}`} />
              <div className={`${styles.skel} ${styles.statValSkel}`} />
            </div>
          ))}
        </div>
        <div className={styles.engRow}>
          <div className={`${styles.skel} ${styles.engLabelSkel}`} />
          <div className={`${styles.skel} ${styles.engNumSkel}`} />
        </div>
        <div className={styles.tagRow}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className={`${styles.skel} ${styles.tagSkel}`} />
          ))}
        </div>
      </div>
    </div>
  );
}
