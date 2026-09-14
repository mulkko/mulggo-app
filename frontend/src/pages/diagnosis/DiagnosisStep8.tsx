import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";
import BottomNav from "../../components/BottomNav/BottomNav";

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
    // dong은 기술창업형(오프라인 매장 아님)이면 비어있는 게 정상(DiagnosisStep5.tsx 참고).
    if (!answers.sido || !answers.sigungu) {
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
        // [2026-09-13, 사용자 확인] 실제로 우수사례 분석이 이뤄지지 않는데 마치 분석
        // 결과인 것처럼 보이는 문구라 주석처리 - 지우지 말고 남겨둠(추후 실제 분석
        // 연동 시 참고).
        // anchor="참고한 우수사례 5건 중 3건이 좌석 이용료+상품 판매 병행 방식을 썼어요."
        title="어떤 방식으로 수익을 만드실 건가요?"
        sub="주요 매출원과 보조 매출원을 구분해 작성해주시면 좋습니다"
        placeholder="예: 음료 판매, 공간 대여(모임룸)"
        initialValue={initialValue}
        onSubmit={handleSubmit}
        onBack={handleBack}
      />

      <BottomNav active="idea" />
    </div>
  );
}

export default DiagnosisStep8;
