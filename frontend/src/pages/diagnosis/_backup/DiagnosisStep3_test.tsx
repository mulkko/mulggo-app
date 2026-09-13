import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosis.module.css";
import DiagnosisHeader from "../DiagnosisHeader";
import DiagnosisTextQuestion from "../DiagnosisTextQuestion";

/**
 * [개인 디자인 확인용, 원본 DiagnosisStep3.tsx(Q4 · 해결 방식)의 격리 사본] 이전 단계
 * 답변 없이 바로 진입 가능 - 세션/백엔드 의존 없음(패턴은 DiagnosisSelect_test.tsx와 동일).
 */
function DiagnosisStep3_test() {
  const navigate = useNavigate();

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/home")} pct="67%" stepLabel="AI 제안 · 4/6 [TEST]" />
      <DiagnosisTextQuestion
        topicBadge="Q4 · 해결 방식"
        title="이 문제를 어떤 제품이나 서비스로 해결하실 건가요?"
        initialValue=""
        onSubmit={() => {}}
        onBack={() => navigate("/home")}
      />
    </div>
  );
}

export default DiagnosisStep3_test;
