import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import { consumeDiagnosisReturnTo, getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";
import BottomNav from "../../components/BottomNav/BottomNav";

/**
 * 사업구체화 진단 1/5 — "구체화 진단1" = Q1 (dev_links.html 목업 이름).
 * 슬롯 0(시드, 자유입력). /diagnosis/choice 다음으로 바로 들어오는 첫 질문이라
 * 이전 단계 답변 의존성이 없다.
 */
function DiagnosisStep1() {
  const [initialValue] = useState(() => getDiagnosisAnswers().seedInterest ?? "");
  const navigate = useNavigate();

  const handleBack = () => navigate("/diagnosis/choice");

  const handleSubmit = (value: string) => {
    saveDiagnosisAnswers({ seedInterest: value });
    const returnTo = consumeDiagnosisReturnTo();
    navigate(returnTo ?? "/diagnosis/select");
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="25%" stepLabel="1/6" />
      <DiagnosisTextQuestion
        topicBadge="Q1 · 사업 아이템 구상"
        title="구상 중인 사업 아이디어를 편하게 적어주세요."
        sub="아직 막연한 관심사나 문제의식 단계여도 괜찮아요."
        initialValue={initialValue}
        onSubmit={handleSubmit}
        onBack={handleBack}
      />

      <BottomNav active="idea" />
    </div>
  );
}

export default DiagnosisStep1;
