import styles from "../../styles/diagnosis.module.css";

interface DiagnosisHeaderProps {
  onBack: () => void;
  pct: string;
  stepLabel: string;
}

/** 진단 화면이 공유하는 헤더 (뒤로가기 + 진행바 + 단계뱃지) — ideaQuestions.module.css의 header 구조 포팅. */
function DiagnosisHeader({ onBack, pct, stepLabel }: DiagnosisHeaderProps) {
  return (
    <header className={styles.header}>
      <button type="button" className={styles.backButton} onClick={onBack} aria-label="뒤로가기">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M16 5l-8 7 8 7" />
        </svg>
      </button>
      <div className={styles.progressTrack}>
        <div className={styles.progressFill} style={{ width: pct }} />
      </div>
      <span className={styles.stepBadge}>{stepLabel}</span>
    </header>
  );
}

export default DiagnosisHeader;
