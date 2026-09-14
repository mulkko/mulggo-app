import { useNavigate } from "react-router-dom";
import logo from "../../assets/logo.svg";
import styles from "../../styles/diagnosisReportSummary.module.css";
import BottomNav from "../../components/BottomNav/BottomNav";

/**
 * [2026-09-13, 개인 확인용] report-summary-preview 화면의 헤더/서브헤더/하단버튼
 * 레이아웃 구조는 그대로 유지하고(사용자 확인 - "header 영역이 레이아웃"), 스크롤
 * 콘텐츠 영역 안쪽 내용만 빈 자리로 비웠다(사용자 확인 - "콘텐츠 영역 내용만 지우라고
 * 했지"). 하단에는 Home.tsx 등이 쓰는 진짜 BottomNav 컴포넌트를 그대로 추가.
 * 라이브 .page는 min-height:100vh라서 내용이 길어지면 페이지 전체가 늘어나 하단이
 * 화면 밖으로 밀려난다 - 여기서는 바깥 div에 인라인 style로 height:100vh +
 * overflow:hidden만 덮어써서 .scrollArea(flex:1, overflow-y:auto)가 안쪽에서만
 * 스크롤되게 만든다.
 */
function DiagnosisReportSummaryFixedLayoutTest() {
  const navigate = useNavigate();
  const handleBack = () => navigate("/home");
  const handleMatch = () => navigate("/home");

  return (
    <div className={`pageContainer ${styles.page}`} style={{ height: "100vh", overflow: "hidden" }}>
      <header className={styles.header}>
        <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M16 5l-8 7 8 7" />
          </svg>
        </button>
        {/* [2026-09-13, 개인 확인용] 라이브(diagnosisReportSummary.module.css)의
            .brandName은 flex:1이라 로고가 헤더 맨 끝으로 밀려난다 - 이 테스트에서만
            로고를 글자 바로 옆에 붙이려고 flex를 꺼서 로컬로 오버라이드(공용 CSS는
            안 건드림). */}
        <span className={styles.brandName} style={{ flex: "none" }}>MULKKO REPORT</span>
        <img src={logo} alt="물꼬 로고" className={styles.logoMark} />
      </header>

      <div className={styles.subHeader}>이렇게 정리했어요</div>

      <div className={styles.scrollArea}>
        <div className={styles.summaryCard} />
        <div className={styles.heading} />
        <div className={styles.ideaCard} />
        <div className={styles.ideaCard} />
        <div className={styles.ideaCard} />
      </div>

      <div className={styles.footer}>
        <button type="button" className={styles.prevButton} onClick={handleBack}>
          이전
        </button>
        <button type="button" className={styles.matchButton} onClick={handleMatch}>
          지원사업 매칭 보기 →
        </button>
      </div>

      <BottomNav active="home" />
    </div>
  );
}

export default DiagnosisReportSummaryFixedLayoutTest;
