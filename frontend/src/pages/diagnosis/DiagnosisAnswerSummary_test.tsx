import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";

/**
 * [개인 테스트용, 원본 DiagnosisAnswerSummary.tsx의 격리 사본] sessionStorage/이전 단계
 * 의존 없이 목업 데이터로 바로 렌더링만 확인하는 페이지. 정식 흐름과 완전히 분리돼
 * 있어서 주소창에 바로 쳐서 들어가도 리다이렉트 안 됨(2026-09-12, 사용자 확인 - 병합
 * 충돌로 실제 흐름과 연결이 끊겼던 DiagnosisPsstConfirm 사례처럼 "확인이 안 된다"는
 * 문제를 피하려고 아예 독립된 사본으로 둠).
 */
function DiagnosisAnswerSummary_test() {
  const navigate = useNavigate();

  const rows = [
    { label: "Q1 · 사업 아이템", value: "동네에 스페셜티 커피를 마실 곳이 없어서 아쉬웠다" },
    { label: "Q2 · 출발점", value: "① 불편했던 경험에서 (문제 해결형)" },
    { label: "Q3 · 문제 정의", value: "원두 품질 낮은 카페뿐이라는 점" },
    { label: "Q4 · 해결 방식", value: "직접 로스팅한 원두로 에스프레소를 만들어 판매한다" },
    { label: "Q5 · 매장 운영 형태", value: "① 고객 방문형 오프라인 매장·공간" },
    { label: "Q6 · 지역·규모", value: "서울특별시 종로구 청운효자동" },
  ];

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/home")} pct="100%" stepLabel="AI 제안 · 답변 정리 [TEST]" />
      <div className={styles.scrollArea}>
        <h1 className={styles.questionTitle}>지금까지 답변한 내용이에요</h1>
        <p className={styles.questionSub}>이 내용을 바탕으로 업종코드를 매칭하고 분석 리포트를 준비했어요.</p>
        <div className={styles.cardList}>
          {rows.map((row) => (
            <div key={row.label} className={styles.confirmCard}>
              <span className={styles.confirmCardLabel}>{row.label}</span>
              <span className={styles.confirmCardValue}>{row.value || "-"}</span>
            </div>
          ))}
        </div>
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={() => navigate("/home")}>
          홈으로
        </button>
        <button type="button" className={styles.nextButton} onClick={() => navigate("/diagnosis/report-test")}>
          분석 리포트 보기 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisAnswerSummary_test;
