import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosis.module.css";
import DiagnosisHeader from "../DiagnosisHeader";
import DiagnosisTextQuestion from "../DiagnosisTextQuestion";

/**
 * [개인 디자인 확인용, 원본 DiagnosisStep8.tsx(Q9 · 수익모델)의 격리 사본] 세션 없이
 * 바로 확인(패턴은 DiagnosisStep6_test.tsx와 동일).
 */
function DiagnosisStep8_test() {
  const navigate = useNavigate();

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/home")} pct="75%" stepLabel="선택 질문 · 3/4 [TEST]" />
      <DiagnosisTextQuestion
        topicBadge="Q9 · 수익모델"
        anchor="참고한 우수사례 5건 중 3건이 좌석 이용료+상품 판매 병행 방식을 썼어요."
        title="어떤 방식으로 수익을 만드실 건가요?"
        sub="주요 매출원과 보조 매출원을 구분해 작성해주시면 좋습니다"
        placeholder="예: 음료 판매, 공간 대여(모임룸)"
        required={false}
        onSubmit={() => {}}
        onBack={() => navigate("/home")}
      />
    </div>
  );
}

export default DiagnosisStep8_test;
