import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";

/**
 * [개인 테스트용, 원본 DiagnosisPsstConfirm.tsx의 격리 사본] sessionStorage/이전 단계
 * 의존 없이 목업 데이터로 바로 렌더링만 확인하는 페이지. 정식 흐름과 완전히 분리돼
 * 있어서 주소창에 바로 쳐서 들어가도 리다이렉트 안 됨(2026-09-12, 사용자 확인 -
 * DiagnosisAnswerSummary_test.tsx와 동일한 이유/패턴).
 */
function DiagnosisPsstConfirm_test() {
  const navigate = useNavigate();

  const cards = [
    { label: "Q1 · 사업 아이템", value: "동네에 스페셜티 커피를 마실 곳이 없어서 아쉬웠다" },
    { label: "Q2 · 출발점", value: "① 불편했던 경험에서 (문제 해결형)" },
    { label: "Q3 · 문제 정의", value: "원두 품질 낮은 카페뿐이라는 점" },
    { label: "Q4 · 해결 방식", value: "직접 로스팅한 원두로 에스프레소를 만들어 판매한다" },
    { label: "Q5 · 매장 운영 형태", value: "① 고객 방문형 오프라인 매장·공간" },
    { label: "Q6 · 지역·규모", value: "서울특별시 종로구 청운효자동" },
  ];

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/home")} pct="100%" stepLabel="PSST 확정 [TEST]" />
      <div className={styles.scrollArea}>
        <h1 className={styles.questionTitle}>이렇게 정리했어요, 확인해주세요</h1>
        <p className={styles.questionSub}>채워진 항목을 눌러서 언제든 수정할 수 있어요</p>
        <div className={styles.cardList}>
          {cards.map((card) => (
            <div key={card.label} className={styles.confirmCard}>
              <span className={styles.confirmCardLabel}>{card.label}</span>
              <span className={styles.confirmCardValue}>{card.value}</span>
            </div>
          ))}
        </div>
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={() => navigate("/home")}>
          홈으로
        </button>
        <button type="button" className={styles.nextButton} onClick={() => {}}>
          확정 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisPsstConfirm_test;
