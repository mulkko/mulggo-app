import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import { consumeDiagnosisReturnTo, getDiagnosisAnswers, saveDiagnosisAnswers, type Origin } from "./diagnosisAnswers";
import BottomNav from "../../components/BottomNav/BottomNav";

/**
 * 사업구체화 진단 2/5 — "진단방식선택" = Q2 (dev_links.html 목업 이름, 프로토타입 qMeta.q1/Q2).
 * 슬롯 0-1(출발점 분기): 문제해결형/기회추구형 중 하나를 고른다. Q1(구체화 진단1)
 * 다음 순서라 seedInterest 없이 바로 들어오면 진행 순서가 안 맞으므로 Q1로 되돌린다.
 * 저장 구조는 두 유형이 완전히 동일하고, 이후 화면(구체화 진단2·3)의 질문 문구만
 * 갈린다(PDF 4장) - 데이터 처리엔 영향 없음.
 */
function DiagnosisSelect() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Origin | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.seedInterest) {
      navigate("/diagnosis/1", { replace: true });
      return;
    }
    setSelected(answers.origin ?? null);
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/1");

  const choose = (origin: Origin) => {
    saveDiagnosisAnswers({ origin });
    const returnTo = consumeDiagnosisReturnTo();
    navigate(returnTo ?? "/diagnosis/3");
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="40%" stepLabel="2/6" />

      <div className={styles.scrollArea}>
        <h1 className={styles.questionTitle}>이 아이디어는 어디서 출발했나요?</h1>
        <p className={styles.questionSub}>두 갈래 중 가까운 쪽을 골라주세요.</p>

        <span className={styles.topicBadge}>Q2 · 출발점</span>

        <div className={styles.cardList}>
          <button type="button" className={styles.radioCard} onClick={() => setSelected("problem")}>
            <span className={styles.radioCardHead}>
              <span className={styles.radioCardTitle}>① &quot;불편했던 경험에서&quot;</span>
              <span className={styles.radioCardDesc}>문제 해결형</span>
            </span>
            <span className={styles.radioDot}>
              {selected === "problem" && <span className={styles.radioDotOn} />}
            </span>
          </button>
          <button type="button" className={styles.radioCard} onClick={() => setSelected("opportunity")}>
            <span className={styles.radioCardHead}>
              <span className={styles.radioCardTitle}>② &quot;이런 게 있으면 좋겠다&quot;</span>
              <span className={styles.radioCardDesc}>기회 추구형</span>
            </span>
            <span className={styles.radioDot}>
              {selected === "opportunity" && <span className={styles.radioDotOn} />}
            </span>
          </button>
        </div>
      </div>

      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={handleBack}>
          이전
        </button>
        <button
          type="button"
          className={styles.nextButton}
          disabled={selected === null}
          onClick={() => selected && choose(selected)}
        >
          다음 →
        </button>
      </div>

      <BottomNav active="idea" />
    </div>
  );
}

export default DiagnosisSelect;
