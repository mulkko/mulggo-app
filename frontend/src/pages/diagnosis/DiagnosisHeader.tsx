import styles from "../../styles/diagnosis.module.css";
import logo from "../../assets/logo.svg";

interface DiagnosisHeaderProps {
  onBack: () => void;
  pct: string;
  stepLabel: string;
  /** [2026-09-13, 사용자 확인] /diagnosis/industry-result처럼 "다음 질문으로 이어지는
   * 단계"가 아닌 결과 화면에서 진행률 바+단계뱃지 행 자체를 없애고 싶을 때 true. */
  hideProgress?: boolean;
}

/**
 * 진단 질응답 화면(Q1~Q9 + 업종코드 매칭/답변정리)이 공유하는 헤더.
 * [2026-09-13, 사용자 확인] "MULKKO IDEA" 브랜드 행을 상단에 새로 추가하고(다른
 * 화면들의 .reportHeaderTop/.logo/.logoText/.logoMark와 동일 스펙 재사용, 문구만
 * 다름 - DiagnosisReport.tsx의 "MULKKO REPORT" 패턴 참고), 기존 진행바+단계뱃지는
 * 그 아래 행으로 내렸다. 이 그룹은 질응답 흐름이라 하단 네비게이션(BottomNav)은
 * 넣지 않는다(사용자 확인).
 */
function DiagnosisHeader({ onBack, pct, stepLabel, hideProgress }: DiagnosisHeaderProps) {
  return (
    <>
      <div className={styles.reportHeaderTop}>
        <button type="button" className={styles.backButton} onClick={onBack} aria-label="뒤로가기">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M16 5l-8 7 8 7" />
          </svg>
        </button>
        <span className={styles.logo}>
          <span className={styles.logoText}>MULKKO IDEA</span>
          <img src={logo} alt="물꼬 로고" className={styles.logoMark} />
        </span>
      </div>
      {!hideProgress && (
        <div className={styles.header}>
          <div className={styles.progressTrack}>
            <div className={styles.progressFill} style={{ width: pct }} />
          </div>
          <span className={styles.stepBadge}>{renderStepLabel(stepLabel)}</span>
        </div>
      )}
    </>
  );
}

// [2026-09-13, 사용자 확인] "N/6" 형식(Step1~5)일 때 "총 페이지 중 현재 페이지 번호"인
// 앞자리(N)만 더 진한 색으로 구분해 보여준다 - "업종코드 매칭"/"답변 정리"처럼 숫자가
// 아닌 라벨은 그냥 그대로 보여준다.
function renderStepLabel(stepLabel: string) {
  const match = /^(\d+)(\/\d+)$/.exec(stepLabel);
  if (!match) return stepLabel;
  const [, current, rest] = match;
  return (
    <>
      <span className={styles.stepBadgeCurrent}>{current}</span>
      {rest}
    </>
  );
}

export default DiagnosisHeader;
