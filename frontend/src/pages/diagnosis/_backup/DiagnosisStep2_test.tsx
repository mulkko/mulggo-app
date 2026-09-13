import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosis.module.css";
import DiagnosisHeader from "../DiagnosisHeader";
import DiagnosisTextQuestion from "../DiagnosisTextQuestion";

/**
 * [개인 디자인 확인용, 원본 DiagnosisStep2.tsx(Q3 · 문제 정의)의 격리 사본] 이전 단계
 * 답변 없이 바로 진입 가능 - 세션/백엔드 의존 없음(패턴은 DiagnosisSelect_test.tsx와 동일).
 */
function DiagnosisStep2_test() {
  const navigate = useNavigate();

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/home")} pct="60%" stepLabel="AI 제안 · 3/6 [TEST]" />
      <DiagnosisTextQuestion
        topicBadge="Q3 · 문제 정의"
        title="고객이 겪고 있는 문제는 구체적으로 무엇인가요?"
        initialValue=""
        onSubmit={() => {}}
        onBack={() => navigate("/home")}
      />
    </div>
  );
}

export default DiagnosisStep2_test;
