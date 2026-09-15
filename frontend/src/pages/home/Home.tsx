import { useNavigate } from "react-router-dom";
import styles from "../../styles/home.module.css";
import BottomNav from "../../components/BottomNav/BottomNav";
import ChatFab from "../../components/ChatFab/ChatFab";

/**
 * 홈 화면(/home).
 *
 * 상단 영역(헤더/배지/헤드라인/설명/CTA/로그인 링크)은 프로토타입 is.home 블록의
 * 실측값을 그대로 옮긴 것이라 문구·수치를 임의로 바꾸지 않는다.
 *
 * "HOW IT WORKS" 섹션은 원본 문구는 100% 유지하되 레이아웃만 새 스펙(민트 박스 +
 * 흰색 카드 3분리 + 단계별 단순 아이콘)으로 교체했다.
 *
 * [2026-09-15, 사용자 확인] "로그인 안 하면 서비스 자체를 못 쓴다" 원칙으로
 * App.tsx가 이 라우트를 RequireAuth로 감싸서, 이 컴포넌트는 항상 로그인된
 * 상태로만 렌더된다 - 로그인 여부 분기(비로그인용 회원가입/로그인 버튼, 조건부
 * BottomNav)를 없애고 로그인 상태 UI만 남김.
 */

/**
 * HOW IT WORKS 3단계.
 * title/desc 문구는 프로토타입 원본 그대로 — 수정 금지.
 * 카드 구조는 "번호 배지 → 제목 → 설명" 세로 1단 (추가 아이콘 없음).
 */
const HOW_IT_WORKS = [
  {
    title: "짧은 질문으로 사업 구체화",
    desc: "관심분야·경험을 입력하면 물꼬 AI가 방향을 제안해요.",
  },
  {
    title: "업종코드 자동 매칭 + 맞춤 분석",
    desc: "상권분석 또는 기술창업 분석으로 자동 연결해 드려요.",
  },
  {
    title: "정부지원사업 매칭 + 신청 도우미",
    desc: "물꼬 AI 어시스턴트가 신청서 작성까지 도와드려요.",
  },
];

function Home() {
  const navigate = useNavigate();

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* ===== 헤더 (실측: 52px, space-between) ===== */}
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.brandName}>LET'S MULKKO</span>
          <span className={styles.brandTagline}>창업의 물꼬를 트다</span>
        </div>
      </header>

      {/* ===== 본문 (실측: padding 10px 22px 32px, 세로 gap 22) ===== */}
      <div className={styles.body}>
        <span className={styles.badge}>
          사업구체화 · 정부지원사업 매칭 · 성장 로드맵
        </span>

        <h1 className={styles.headline}>
          막연한 아이디어를
          <br />
          사업 구체화부터
          <br />
          지원사업 매칭까지
        </h1>

        <p className={styles.desc}>
          짧은 질문에 답하면 AI가 사업을 구체화하고, 업종코드에 맞는 맞춤 분석과
          지원사업까지 이어드려요.
        </p>

        {/* [2026-09-11] 진단 진입점 /diagnosis/choice(빠른매칭 vs 정밀구체화) → /diagnosis/1(Q1) →
            /diagnosis/select(Q2) → /diagnosis/3~10. 업종코드 매칭/분석 리포트 연결은 아직 준비 중이라
            질문 흐름까지만 동작함. */}
        <button
          type="button"
          className={styles.signupBtn}
          onClick={() => navigate("/diagnosis/choice")}
        >
          아이디어 구체화하기 →
        </button>
        <button
          type="button"
          className={styles.signupBtn2}
          onClick={() => navigate("/matching")}
        >
          맞춤 지원사업 찾아보기 →
        </button>

        {/* ===== HOW IT WORKS (레이아웃만 교체, 문구는 원본 유지) ===== */}
        <section className={styles.howBox}>
          <div className={styles.howHead}>
            <span className={styles.howLabel}>HOW IT WORKS</span>
            <h2 className={styles.howTitle}>3단계로 끝나는 창업 준비</h2>
          </div>

          <ol className={styles.howCards}>
            {HOW_IT_WORKS.map((step, i) => (
              <li key={step.title} className={styles.howCard}>
                <span className={styles.howNum}>{i + 1}</span>
                <div className={styles.howCardBody}>
                  <p className={styles.howCardTitle}>{step.title}</p>
                  <p className={styles.howCardDesc}>{step.desc}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <ChatFab variant="withBottomNav" />
      <BottomNav active="home" />
    </div>
  );
}

export default Home;
