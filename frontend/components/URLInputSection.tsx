'use client';

import { useState } from 'react';
import styles from './URLInputSection.module.css';

interface URLInputSectionProps {
  onAnalyze: (urlA: string, urlB: string) => void;
  isLoading: boolean;
}

// ── URL validators ─────────────────────────────────────────────────────────
function isValidYouTubeUrl(url: string): boolean {
  return /^(https?:\/\/)?(www\.)?(youtube\.com\/(watch\?.*v=|shorts\/|embed\/)|youtu\.be\/)[\w-]+/.test(url);
}

function isValidInstagramUrl(url: string): boolean {
  // Accepts /reel/, /reels/, and /p/ paths
  return /^(https?:\/\/)?(www\.)?instagram\.com\/(reels?|p)\/[\w-]+/.test(url);
}

function isValidSocialUrl(url: string): boolean {
  return isValidYouTubeUrl(url) || isValidInstagramUrl(url);
}

type Platform = 'youtube' | 'instagram' | null;

function detectPlatform(url: string): Platform {
  if (isValidYouTubeUrl(url)) return 'youtube';
  if (isValidInstagramUrl(url)) return 'instagram';
  return null;
}

// ── Sub-components ─────────────────────────────────────────────────────────
interface PlatformBadgeProps {
  platform: Platform;
  label: 'A' | 'B';
}

function PlatformBadge({ platform, label }: PlatformBadgeProps) {
  if (platform === 'youtube') {
    return (
      <span className={styles.platformBadge} data-platform="youtube">
        ▶ YouTube — Video {label}
      </span>
    );
  }
  if (platform === 'instagram') {
    return (
      <span className={styles.platformBadge} data-platform="instagram">
        ◉ Instagram — Video {label}
      </span>
    );
  }
  return (
    <span className={styles.platformBadge} data-platform="generic">
      ◈ Video {label}
    </span>
  );
}

// ── Main component ─────────────────────────────────────────────────────────
export default function URLInputSection({ onAnalyze, isLoading }: URLInputSectionProps) {
  const [urlA, setUrlA] = useState('');
  const [urlB, setUrlB] = useState('');
  const [aTouched, setATouched] = useState(false);
  const [bTouched, setBTouched] = useState(false);
  const [aFocused, setAFocused] = useState(false);
  const [bFocused, setBFocused] = useState(false);

  const aValid = isValidSocialUrl(urlA);
  const bValid = isValidSocialUrl(urlB);
  const canSubmit = aValid && bValid && !isLoading;

  const platformA = detectPlatform(urlA);
  const platformB = detectPlatform(urlB);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setATouched(true);
    setBTouched(true);
    if (canSubmit) {
      onAnalyze(urlA, urlB);
    }
  };

  const getInputState = (
    value: string,
    isValid: boolean,
    isTouched: boolean,
    isFocused: boolean,
  ) => {
    if (isFocused) return 'focused';
    if (!value) return 'empty';
    if (isTouched && !isValid) return 'error';
    if (isValid) return 'valid';
    return 'empty';
  };

  const aState = getInputState(urlA, aValid, aTouched, aFocused);
  const bState = getInputState(urlB, bValid, bTouched, bFocused);

  return (
    <div className={styles.wrapper}>
      <div className={styles.hero}>
        <div className={styles.heroIcon}>◈</div>
        <h1 className={styles.heroTitle}>
          Compare Any Two Videos with <span className={styles.gradientText}>AI</span>
        </h1>
        <p className={styles.heroSub}>
          Paste two video URLs — YouTube, Instagram Reel, or any mix.
          VibeRAG analyzes transcripts, metadata, and engagement, then lets you chat with the data.
        </p>
      </div>

      <form onSubmit={handleSubmit} className={styles.form} noValidate>
        {/* Video A Input */}
        <div className={`${styles.inputGroup} ${styles[`state_${aState}`]}`}>
          <label className={styles.label} htmlFor="url-a">
            <PlatformBadge platform={platformA} label="A" />
            <span className={styles.labelSub}>YouTube or Instagram</span>
          </label>
          <div className={styles.inputWrap}>
            <input
              id="url-a"
              className={styles.input}
              type="url"
              placeholder="https://youtube.com/watch?v=... or instagram.com/reels/..."
              value={urlA}
              onChange={(e) => setUrlA(e.target.value)}
              onFocus={() => setAFocused(true)}
              onBlur={() => { setAFocused(false); setATouched(true); }}
              disabled={isLoading}
              autoComplete="off"
            />
            {aState === 'valid' && <span className={styles.checkmark}>✓</span>}
            {aState === 'error' && <span className={styles.errorIcon}>✕</span>}
          </div>
          {aState === 'error' && (
            <p className={styles.errorMsg}>
              Please enter a valid YouTube or Instagram Reel URL
            </p>
          )}
        </div>

        {/* Video B Input */}
        <div className={`${styles.inputGroup} ${styles[`state_${bState}`]}`}>
          <label className={styles.label} htmlFor="url-b">
            <PlatformBadge platform={platformB} label="B" />
            <span className={styles.labelSub}>YouTube or Instagram</span>
          </label>
          <div className={styles.inputWrap}>
            <input
              id="url-b"
              className={styles.input}
              type="url"
              placeholder="https://youtube.com/watch?v=... or instagram.com/reels/..."
              value={urlB}
              onChange={(e) => setUrlB(e.target.value)}
              onFocus={() => setBFocused(true)}
              onBlur={() => { setBFocused(false); setBTouched(true); }}
              disabled={isLoading}
              autoComplete="off"
            />
            {bState === 'valid' && <span className={styles.checkmark}>✓</span>}
            {bState === 'error' && <span className={styles.errorIcon}>✕</span>}
          </div>
          {bState === 'error' && (
            <p className={styles.errorMsg}>
              Please enter a valid YouTube or Instagram Reel URL
            </p>
          )}
        </div>

        <button
          type="submit"
          className={`${styles.cta} ${isLoading ? styles.loading : ''}`}
          disabled={!canSubmit && !isLoading}
        >
          {isLoading ? (
            <>
              <span className={styles.spinner} />
              Fetching &amp; Analyzing…
            </>
          ) : (
            <>
              <span>⚡</span>
              Analyze Videos
            </>
          )}
        </button>
      </form>
    </div>
  );
}
