import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosisMarketReport.module.css";
import diagnosisStyles from "../../../styles/diagnosis.module.css";

/**
 * [개인 테스트용, 원본 DiagnosisMarketReport.tsx의 격리 사본] sessionStorage 의존과
 * 실제 백엔드 호출(/analysis/market) 둘 다 없이 목업 데이터로 바로 렌더링만 확인하는
 * 페이지. 정식 흐름과 완전히 분리돼 있어서 주소창에 바로 쳐서 들어가도 리다이렉트
 * 안 됨(2026-09-12, 사용자 확인 - DiagnosisAnswerSummary_test.tsx와 동일 패턴).
 */
const MOCK_DONG = "합정동";
const MOCK_INDUSTRY_MIX = [
  { 업종명: "카페", 업체수: 42 },
  { 업종명: "일반음식점", 업체수: 31 },
  { 업종명: "편의점", 업체수: 12 },
  { 업종명: "미용실", 업체수: 8 },
];
const MOCK_FOOTFALL_SCORE = 78;
const MOCK_FOOTFALL_BASIS = "인근 행정동 평균 대비 유동인구 상위 20% 수준";
const MOCK_RESIDENT_POPULATION = 15234;

function DiagnosisMarketReport_test() {
  const navigate = useNavigate();
  const showFootfallTip = false;

  const handleBack = () => navigate("/home");
  const handleNext = () => {};

  const maxIndustryCount = Math.max(0, ...MOCK_INDUSTRY_MIX.map((item) => item.업체수));

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M16 5l-8 7 8 7" />
            </svg>
          </button>
          <span className={styles.headerTitle}>상권분석 리포트 [TEST]</span>
        </div>
      </header>

      <div className={styles.scrollArea}>
        <h1 className={styles.regionTitle}>{MOCK_DONG} 주변 상권 동향</h1>

        <div className={styles.statGrid}>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>반경 500m 동일 업종</span>
            <span className={styles.statValueEmpty}>업종코드 확인 후 표시돼요</span>
          </div>

          <div className={styles.statCard}>
            <button type="button" className={styles.infoButton} aria-label="생활인구지수 설명" aria-pressed={showFootfallTip}>
              ?
            </button>
            <span className={styles.statLabel}>생활인구지수</span>
            <span className={`${styles.statValue} ${styles.statValueAccent}`}>{MOCK_FOOTFALL_SCORE}</span>
          </div>

          <div className={styles.statCard}>
            <span className={styles.statLabel}>상주인구수</span>
            <span className={styles.statValue}>{MOCK_RESIDENT_POPULATION.toLocaleString()}명</span>
          </div>

          <div className={`${styles.statCard} ${styles.statCardHighlight}`}>
            <span className={styles.statLabel}>매칭 지원사업 수</span>
            <span className={styles.statValueEmpty}>업종코드 매칭 후 표시돼요</span>
          </div>
        </div>

        <section className={styles.sectionCard}>
          <h2 className={styles.sectionTitle}>동일 행정동 내 상위 업종 분포</h2>
          {MOCK_INDUSTRY_MIX.map((item) => (
            <div key={item.업종명} className={styles.barRow}>
              <span className={styles.barLabel}>{item.업종명}</span>
              <span className={styles.barTrack}>
                <span
                  className={`${styles.barFill} ${item.업체수 === maxIndustryCount ? styles.barFillMax : ""}`}
                  style={{ width: `${(item.업체수 / maxIndustryCount) * 100}%` }}
                />
              </span>
              <span className={styles.barCount}>{item.업체수}</span>
            </div>
          ))}
        </section>

        <section className={styles.sectionCard}>
          <h2 className={styles.sectionTitle}>동일업종 밀집도</h2>
          <p className={styles.emptyText}>업종코드 확인 후 표시돼요. (참고: {MOCK_FOOTFALL_BASIS})</p>
        </section>
      </div>

      <div className={diagnosisStyles.bottom}>
        <button type="button" className={diagnosisStyles.prevButton} onClick={handleBack}>
          홈으로
        </button>
        <button type="button" className={diagnosisStyles.nextButton} onClick={handleNext}>
          다음 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisMarketReport_test;
