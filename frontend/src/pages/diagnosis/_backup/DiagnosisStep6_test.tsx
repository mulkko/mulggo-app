import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosis.module.css";
import DiagnosisHeader from "../DiagnosisHeader";
import DiagnosisTextQuestion from "../DiagnosisTextQuestion";

/**
 * [개인 디자인 확인용, 원본 DiagnosisStep6.tsx(Q7 · 타깃)의 격리 사본] 세션/실측 앵커
 * 데이터 없이 목업 앵커 문구로 바로 확인(2026-09-13, 사용자 확인 - 나머지 _test 사본과
 * 동일 패턴).
 */
function DiagnosisStep6_test() {
  const navigate = useNavigate();

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/home")} pct="25%" stepLabel="선택 질문 · 1/4 [TEST]" />
      <DiagnosisTextQuestion
        topicBadge="Q7 · 타깃"
        anchor="유사 벤처인증기업 27개 중 연구개발형이 44%로 가장 많아요."
        title="이 문제를 가장 크게 겪는 고객층은 누구인가요?"
        sub="타깃을 구체적으로 정의할수록 이후 분석·매칭의 정확도가 높아집니다"
        placeholder="예: 동네 직장인, 재택근무자"
        required={false}
        onSubmit={() => {}}
        onBack={() => navigate("/home")}
      />
    </div>
  );
}

export default DiagnosisStep6_test;
