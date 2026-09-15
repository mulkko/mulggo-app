import { useNavigate } from "react-router-dom";
import logo from "../../assets/logo.svg";
import styles from "../../styles/diagnosisChoice.module.css";
import { clearDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";
import BottomNav from "../../components/BottomNav/BottomNav";
import ChatFab from "../../components/ChatFab/ChatFab";
import BackButton from "../../components/BackButton/BackButton";

/**
 * 진단 방식 선택 화면 (`/diagnosis/choice`).
 *
 * 프로토타입 라벨 "05-1 진단 방식 선택" (내부 키 is.ideaChoice).
 * 사업 아이디어 구체화에 들어가기 전, 빠른 매칭 / 정밀 구체화 두 방식 중
 * 하나를 고르는 분기 화면. 두 카드 모두 사업구체화 진단 플로우(Q1, /diagnosis/1)로
 * 이어지고, 질문 자체(1~6번, 필수)는 동일하다 - 갈리는 건 6번(지역) 이후 리포트
 * 화면 다음부터: "빠른 매칭"은 바로 공고매칭리스트로, "정밀 구체화"는 선택
 * 4문항(Q7~Q10)을 더 거친 뒤 공고매칭리스트로 간다(diagnosisAnswers.mode로 분기,
 * 사용자 확인 - DiagnosisReport 참고).
 *
 * 값(색상/radius/shadow)은 webTokens.css 토큰만 사용한다.
 */

function DiagnosisChoice() {
  const navigate = useNavigate();

  // [2026-09-14, 사용자 확인] clearDiagnosisAnswers()는 원래 완주 시(DiagnosisStep9)에만
  // 불렸는데, 중간에 실패/이탈한 이전 시도의 답변이 sessionStorage에 남아있어서 여기서
  // 새로 시작할 때 이전 입력이 그대로 보이는 문제가 있었다 - 시작 시점에도 초기화한다.
  const startFast = () => {
    clearDiagnosisAnswers();
    saveDiagnosisAnswers({ mode: "fast" });
    navigate("/diagnosis/1");
  };

  const startPrecise = () => {
    clearDiagnosisAnswers();
    saveDiagnosisAnswers({ mode: "precise" });
    navigate("/diagnosis/1");
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <BackButton onClick={() => navigate("/home")} />
        <span className={styles.brandName}>MULKKO IDEA</span>
        <img src={logo} alt="물꼬 로고" className={styles.logoMark} />
      </header>

      <main className={styles.body}>
        <div className={styles.heading}>
          <h1 className={styles.title}>사업 아이디어를 함께 구상해요</h1>
          <p className={styles.subtitle}>두 가지 방식 중 편한 쪽을 골라주세요</p>
        </div>

        <button type="button" className={styles.card} onClick={startFast}>
          <span className={styles.cardHead}>
            <span className={styles.cardTitle}>빠른 매칭</span>
            <span className={`${styles.inlineBadge} ${styles.inlineBadgeTeal}`}>
              업종코드 + 분석리포트 + 매칭
            </span>
          </span>
          <span className={styles.cardDesc}>
            핵심 질문 6개만 답하면 사업구체화 과정 없이 업종코드부터 빠르게 확인해요. 정부지원사업
            매칭까지 최단 경로로 이어가요.
          </span>
          <span className={`${styles.pill} ${styles.pillTeal}`}>
            약 1~2분 소요 · 복잡한 과정 없이 매칭까지 최단 경로예요
          </span>
        </button>

        <button type="button" className={`${styles.card} ${styles.cardNavy}`} onClick={startPrecise}>
          <span className={styles.cardHead}>
            <span className={styles.cardTitle}>정밀 구체화</span>
            <span className={`${styles.inlineBadge} ${styles.inlineBadgeNavy}`}>
              업종코드 + 분석리포트 + 구체화 + 매칭
            </span>
          </span>
          <span className={styles.cardDesc}>
            10개 질문에 답하며 사업을 구체화해요. 상권·기술창업분석 데이터와 우수사례를 먼저
            보여드리고, 이 데이터를 참고해 타깃·차별점·수익모델까지 답하도록 도와드려요.
          </span>
          <span className={`${styles.pill} ${styles.pillNavy}`}>
            약 5~7분 소요 · 실측 데이터를 참고해 답변이 더 구체화돼요
          </span>
        </button>
      </main>

      <BottomNav active="idea" />
      <ChatFab variant="top" />
    </div>
  );
}

export default DiagnosisChoice;
