import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosis.module.css";
import DiagnosisHeader from "../DiagnosisHeader";
import DiagnosisTextQuestion from "../DiagnosisTextQuestion";

/**
 * [개인 디자인 확인용, 원본 DiagnosisStep9.tsx(Q10 · 보유역량)의 격리 사본] 세션 없이
 * 질문 입력 화면만 바로 확인 - 제출 후 완료 화면(아이디어 카드)은
 * DiagnosisReportSummaryPreview.tsx(/dev/report-summary-preview)가 이미 따로
 * 담당하고 있어 여기선 다루지 않는다.
 */
function DiagnosisStep9_test() {
  const navigate = useNavigate();

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/home")} pct="92%" stepLabel="선택 질문 · 4/4 [TEST]" />
      <DiagnosisTextQuestion
        topicBadge="Q10 · 보유역량"
        title="이 문제를 해결할 수 있는 본인만의 강점·경험이 있으신가요?"
        sub="자격증, 경력, 네트워크 등 구체적으로 작성해주세요"
        placeholder="예: 바리스타 자격증, 요식업 경력"
        required={false}
        buttonLabel="제출하기"
        onSubmit={() => {}}
        onBack={() => navigate("/home")}
      />
    </div>
  );
}

export default DiagnosisStep9_test;
