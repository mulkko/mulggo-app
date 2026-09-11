import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import { DIAGNOSIS_QUESTIONS, getDiagnosisAnswers, saveDiagnosisAnswers, type Origin } from "./diagnosisAnswers";

/**
 * 사업구체화 진단 4/5 — "구체화 진단3" = Q4 (dev_links.html 목업 이름).
 * 슬롯 5(사업화 방식). 질문 문구는 origin에 따라 갈린다(구체화 진단2와 동일 이유).
 */
function DiagnosisStep3() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [origin, setOrigin] = useState<Origin>("problem");
  const [initialValue, setInitialValue] = useState("");

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.origin || !answers.problemToSolve) {
      navigate("/diagnosis/select", { replace: true });
      return;
    }
    setOrigin(answers.origin);
    setInitialValue(answers.solutionApproach ?? "");
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/2");

  const handleSubmit = (value: string) => {
    saveDiagnosisAnswers({ solutionApproach: value });
    navigate("/diagnosis/4");
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="67%" stepLabel="AI 제안 · 4/6" />
      <DiagnosisTextQuestion
        topicBadge="Q4 · 해결 방식"
        title={DIAGNOSIS_QUESTIONS[origin].solutionApproach}
        initialValue={initialValue}
        onSubmit={handleSubmit}
        onBack={handleBack}
      />
    </div>
  );
}

export default DiagnosisStep3;
