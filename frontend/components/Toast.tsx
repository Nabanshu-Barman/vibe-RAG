'use client';

import { useEffect } from 'react';
import styles from './Toast.module.css';

interface ToastProps {
  message: string;
  type?: 'error' | 'success' | 'info';
  onDismiss: () => void;
}

export default function Toast({ message, type = 'error', onDismiss }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  const icons = { error: '✕', success: '✓', info: 'ℹ' };

  return (
    <div className={`${styles.toast} ${styles[type]}`} role="alert">
      <span className={styles.icon}>{icons[type]}</span>
      <span className={styles.message}>{message}</span>
      <button className={styles.close} onClick={onDismiss} aria-label="Dismiss">✕</button>
    </div>
  );
}
