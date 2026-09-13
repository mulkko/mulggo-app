import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";
import BottomNav from "../../components/BottomNav/BottomNav";

/**
 * 선택 질문 1/4 (Q7 · 타깃). 슬롯: target.
 * [2026-09-13, 사용자 확인] 정밀진단은 Q1~Q10 전부 필수 - "선택 질문"이라는 화면
 * 이름과 달리 실제로는 비워두고 못 넘어가게 한다(DiagnosisTextQuestion 기본값
 * required=true 그대로 사용, 이전엔 required={false}로 열어뒀던 걸 되돌림).
 *
 * [2026-09-11] anchor 문구를 6번(지역) 제출 시 받은 실측 데이터(targetAnchor - 매장형태에
 * 따라 상권분석 또는 벤처통계 기반)로 교체 - 데이터가 없으면(매칭 실패 등) 기존
 * 하드코딩 예시 문구로 대체한다.
 */
function DiagnosisStep6() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [initialValue, setInitialValue] = useState("");
  const [anchor, setAnchor] = useState("유사 벤처인증기업 27개 중 연구개발형이 44%로 가장 많아요.");

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    // dong은 기술창업형(오프라인 매장 아님)이면 비어있는 게 정상(DiagnosisStep5.tsx 참고).
    if (!answers.sido || !answers.sigungu || !answers.sessionId) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setInitialValue(answers.target ?? "");
    if (answers.targetAnchor) setAnchor(answers.targetAnchor);
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/report");

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
        anchor={anchor}
        title="이 문제를 가장 크게 겪는 고객층은 누구인가요?"
        sub="타깃을 구체적으로 정의할수록 이후 분석·매칭의 정확도가 높아집니다"
        placeholder="예: 동네 직장인, 재택근무자"
        initialValue={initialValue}
        onSubmit={handleSubmit}
        onBack={handleBack}
      />

      <BottomNav active="idea" />
    </div>
  );
}

export default DiagnosisStep6;
