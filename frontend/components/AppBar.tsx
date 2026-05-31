import styles from './AppBar.module.css';

interface AppBarProps {
  status: 'idle' | 'analyzing' | 'ready' | 'chatting' | 'error';
}

const STATUS_LABELS: Record<string, string> = {
  idle: 'Ready',
  analyzing: 'Analyzing…',
  ready: 'Videos Loaded',
  chatting: 'Chatting…',
  error: 'Error',
};

export default function AppBar({ status }: AppBarProps) {
  return (
    <header className={styles.appbar}>
      <div className={styles.inner}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>◈</span>
          <span className={styles.logoText}>
            Vibe<span className={styles.logoAccent}>RAG</span>
          </span>
        </div>

        <div className={styles.right}>
          <span className={`${styles.statusPill} ${styles[`status_${status}`]}`}>
            <span className={styles.statusDot} />
            {STATUS_LABELS[status]}
          </span>
        </div>
      </div>
    </header>
  );
}
