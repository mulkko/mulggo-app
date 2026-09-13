import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosis.module.css";
import DiagnosisHeader from "../DiagnosisHeader";
import DiagnosisTextQuestion from "../DiagnosisTextQuestion";

/**
 * [개인 디자인 확인용, 원본 DiagnosisStep7.tsx(Q8 · 차별점)의 격리 사본] 세션/실측 앵커
 * 데이터 없이 목업 앵커 문구로 바로 확인(패턴은 DiagnosisStep6_test.tsx와 동일).
 */
function DiagnosisStep7_test() {
  const navigate = useNavigate();

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/home")} pct="50%" stepLabel="선택 질문 · 2/4 [TEST]" />
      <DiagnosisTextQuestion
        topicBadge="Q8 · 차별점"
        anchor="관련 분야 특허출원이 2021년부터 꾸준히 늘고 있어요."
        title="기존 대안과 비교해 이 사업만의 차별점은 뭐인가요?"
        sub="경쟁 서비스·매장과 비교해 다른 점을 적어주세요"
        placeholder="예: 프랜차이즈 대비 좌석 여유, 조용함"
        required={false}
        onSubmit={() => {}}
        onBack={() => navigate("/home")}
      />
    </div>
  );
}

export default DiagnosisStep7_test;
