import styles from "../../styles/diagnosis.module.css";

interface DiagnosisHeaderProps {
  onBack: () => void;
  stepLabel?: string;
}

/** 진단 5개 화면이 공유하는 헤더 (뒤로가기 + "사업 구체화" 타이틀 + 선택적 단계 표시). */
function DiagnosisHeader({ onBack, stepLabel }: DiagnosisHeaderProps) {
  return (
    <header className={styles.header}>
      <button type="button" className={styles.backButton} onClick={onBack} aria-label="뒤로가기">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M16 5l-8 7 8 7" />
        </svg>
      </button>
      <span className={styles.headerTitle}>사업 구체화</span>
      {stepLabel && <span className={styles.stepLabel}>{stepLabel}</span>}
    </header>
  );
}

export default DiagnosisHeader;
