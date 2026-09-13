import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import {
  consumeDiagnosisReturnTo,
  DIAGNOSIS_QUESTIONS,
  getDiagnosisAnswers,
  saveDiagnosisAnswers,
  type Origin,
} from "./diagnosisAnswers";
import BottomNav from "../../components/BottomNav/BottomNav";

/**
 * 사업구체화 진단 3/5 — "구체화 진단2" = Q3 (dev_links.html 목업 이름).
 * 슬롯 2(문제/기회정의). 질문 문구는 진단방식선택(Q2)에서 고른 origin에 따라 갈린다
 * (데이터 처리엔 영향 없음 - PDF 4장).
 */
function DiagnosisStep2() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [origin, setOrigin] = useState<Origin>("problem");
  const [initialValue, setInitialValue] = useState("");

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.origin || !answers.seedInterest) {
      navigate("/diagnosis/select", { replace: true });
      return;
    }
    setOrigin(answers.origin);
    setInitialValue(answers.problemToSolve ?? "");
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/select");

  const handleSubmit = (value: string) => {
    saveDiagnosisAnswers({ problemToSolve: value });
    const returnTo = consumeDiagnosisReturnTo();
    navigate(returnTo ?? "/diagnosis/4");
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="60%" stepLabel="3/6" />
      <DiagnosisTextQuestion
        topicBadge="Q3 · 문제 정의"
        title={DIAGNOSIS_QUESTIONS[origin].problemToSolve}
        initialValue={initialValue}
        onSubmit={handleSubmit}
        onBack={handleBack}
      />

      <BottomNav active="idea" />
    </div>
  );
}

export default DiagnosisStep2;
