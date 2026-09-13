import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

/**
 * 선택 질문 3/4 (Q9 · 수익모델). 슬롯: revenueModel. DiagnosisStep6와 동일 패턴
 * (가드/필수 여부/스킵 동작 근거는 그쪽 주석 참고).
 */
function DiagnosisStep8() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [initialValue, setInitialValue] = useState("");

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.sido || !answers.sigungu || !answers.dong) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setInitialValue(answers.revenueModel ?? "");
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/8");

  const handleSubmit = (value: string) => {
    saveDiagnosisAnswers({ revenueModel: value });
    navigate("/diagnosis/10");
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="75%" stepLabel="선택 질문 · 3/4" />
      <DiagnosisTextQuestion
        topicBadge="Q9 · 수익모델"
        anchor="참고한 우수사례 5건 중 3건이 좌석 이용료+상품 판매 병행 방식을 썼어요."
        title="어떤 방식으로 수익을 만드실 건가요?"
        sub="주요 매출원과 보조 매출원을 구분해 작성해주시면 좋습니다"
        placeholder="예: 음료 판매, 공간 대여(모임룸)"
        initialValue={initialValue}
        onSubmit={handleSubmit}
        onBack={handleBack}
      />
    </div>
  );
}

export default DiagnosisStep8;
