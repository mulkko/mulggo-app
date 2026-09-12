import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

/**
 * 선택 질문 1/4 (Q7 · 타깃). 슬롯: target.
 * 선택 질문끼리는 서로 비어있을 수 있어 가드 조건으로 못 쓰므로, 필수 질문 구간이
 * 끝났는지(지역·규모까지 채워졌는지)만 확인한다. 값이 비어도 진행 허용
 * (idea_card_generator가 부실 슬롯은 알아서 스킵).
 */
function DiagnosisStep6() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [initialValue, setInitialValue] = useState("");

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.sido || !answers.sigungu || !answers.dong) {
      // Q6(지역·규모) 다음엔 11(PSST 확정)→12(업종코드 매칭)→13(상권분석 리포트)이
      // 이어지는데, 그 화면들도 같은 슬롯(sido/sigungu/dong)을 가드로 쓰므로 여기서는
      // 13으로만 보내도 없으면 알아서 Q6까지 되돌아간다.
      navigate("/diagnosis/market-report", { replace: true });
      return;
    }
    setInitialValue(answers.target ?? "");
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/market-report");

  const handleSubmit = (value: string) => {
    saveDiagnosisAnswers({ target: value });
    navigate("/diagnosis/8");
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="25%" stepLabel="선택 질문 · 1/4" />
      <DiagnosisTextQuestion
        topicBadge="Q7 · 타깃"
        anchor="유사 벤처인증기업 27개 중 연구개발형이 44%로 가장 많아요."
        title="이 문제를 가장 크게 겪는 고객층은 누구인가요?"
        sub="타깃을 구체적으로 정의할수록 이후 분석·매칭의 정확도가 높아집니다"
        placeholder="예: 동네 직장인, 재택근무자"
        initialValue={initialValue}
        required={false}
        onSubmit={handleSubmit}
        onBack={handleBack}
      />
    </div>
  );
}

export default DiagnosisStep6;
