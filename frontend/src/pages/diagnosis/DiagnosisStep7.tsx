import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

/**
 * 선택 질문 2/4 (Q8 · 차별점). 슬롯: differentiator. DiagnosisStep6와 동일 패턴
 * (가드/필수 여부/스킵 동작 근거는 그쪽 주석 참고).
 */
function DiagnosisStep7() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [initialValue, setInitialValue] = useState("");

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.sido || !answers.sigungu || !answers.dong) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setInitialValue(answers.differentiator ?? "");
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/7");

  const handleSubmit = (value: string) => {
    saveDiagnosisAnswers({ differentiator: value });
    navigate("/diagnosis/9");
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="50%" stepLabel="선택 질문 · 2/4" />
      <DiagnosisTextQuestion
        topicBadge="Q8 · 차별점"
        anchor="관련 분야 특허출원이 2021년부터 꾸준히 늘고 있어요."
        title="기존 대안과 비교해 이 사업만의 차별점은 뭐인가요?"
        sub="경쟁 서비스·매장과 비교해 다른 점을 적어주세요"
        placeholder="예: 프랜차이즈 대비 좌석 여유, 조용함"
        initialValue={initialValue}
        required={false}
        onSubmit={handleSubmit}
        onBack={handleBack}
      />
    </div>
  );
}

export default DiagnosisStep7;
