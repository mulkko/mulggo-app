import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosis.module.css";
import DiagnosisHeader from "../DiagnosisHeader";
import type { Origin } from "../diagnosisAnswers";

/**
 * [개인 디자인 확인용, 원본 DiagnosisSelect.tsx의 격리 사본] 이전 단계 답변(seedInterest)
 * 없이 바로 진입해도 리다이렉트 안 되는 사본 - 세션/백엔드 의존 전혀 없음(2026-09-13,
 * 사용자 확인 - 진단 흐름 화면들이 전부 이전 단계 가드가 있어서 직접 URL로 들어가면
 * 계속 앞 단계로 튕겨서 디자인만 따로 확인하기 어렵다는 요청으로 만듦).
 */
function DiagnosisSelect_test() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Origin | null>(null);

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/home")} pct="40%" stepLabel="AI 제안 · 2/6 [TEST]" />

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
        <button type="button" className={styles.prevButton} onClick={() => navigate("/home")}>
          이전
        </button>
        <button type="button" className={styles.nextButton} disabled={selected === null} onClick={() => {}}>
          다음 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisSelect_test;
