import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

/**
 * 사업구체화 진단 2/5 — "구체화 진단1" (dev_links.html 목업 이름).
 * 슬롯 0(시드, 자유입력). origin(출발점) 없이 이 화면에 바로 들어오면 진행 순서가
 * 안 맞으므로 진단방식선택으로 되돌린다.
 */
function DiagnosisStep1() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [initialValue, setInitialValue] = useState("");

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.origin) {
      navigate("/diagnosis/select", { replace: true });
      return;
    }
    setInitialValue(answers.seedInterest ?? "");
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/select");

  const handleSubmit = (value: string) => {
    saveDiagnosisAnswers({ seedInterest: value });
    navigate("/diagnosis/2");
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} stepLabel="1 / 4" />
      <DiagnosisTextQuestion
        title="구상 중인 사업 아이디어를 편하게 적어주세요."
        sub="아직 막연한 관심사나 문제의식 단계여도 괜찮아요."
        initialValue={initialValue}
        onSubmit={handleSubmit}
      />
    </div>
  );
}

export default DiagnosisStep1;
