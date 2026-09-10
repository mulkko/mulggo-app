import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import { saveDiagnosisAnswers, type Origin } from "./diagnosisAnswers";

/**
 * 사업구체화 진단 1/5 — "진단방식선택" (dev_links.html 목업 이름).
 * 슬롯 0-1(출발점 분기): 문제해결형/기회추구형 중 하나를 고른다.
 * 저장 구조는 두 유형이 완전히 동일하고, 이후 화면(구체화 진단2·3)의 질문 문구만
 * 갈린다(PDF 4장) - 데이터 처리엔 영향 없음.
 */
function DiagnosisSelect() {
  const navigate = useNavigate();

  const handleBack = () => {
    // 진단 진입점은 /idea/choice(빠른매칭 vs 정밀구체화) — 그쪽으로 되돌린다.
    navigate("/idea/choice");
  };

  const choose = (origin: Origin) => {
    saveDiagnosisAnswers({ origin });
    navigate("/diagnosis/1");
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} />

      <div className={styles.scrollArea}>
        <h1 className={styles.questionTitle}>이 아이디어는 어디서 출발했나요?</h1>
        <p className={styles.questionSub}>두 갈래 중 가까운 쪽을 골라주세요.</p>

        <div className={styles.cardList}>
          <button type="button" className={styles.choiceCard} onClick={() => choose("problem")}>
            <span className={styles.choiceCardTitle}>불편했던 경험에서</span>
            <span className={styles.choiceCardDesc}>문제 해결형 — 겪었던 불편함에서 출발해요</span>
          </button>
          <button type="button" className={styles.choiceCard} onClick={() => choose("opportunity")}>
            <span className={styles.choiceCardTitle}>&quot;이런 게 있으면 좋겠다&quot;는 바람에서</span>
            <span className={styles.choiceCardDesc}>기회 추구형 — 있었으면 하는 바람에서 출발해요</span>
          </button>
        </div>
      </div>
    </div>
  );
}

export default DiagnosisSelect;
