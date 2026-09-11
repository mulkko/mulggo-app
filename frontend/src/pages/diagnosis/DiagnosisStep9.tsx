import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import { authHeaders } from "../../auth/session";
import { clearDiagnosisAnswers, getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface IdeaCard {
  axis: string;
  title: string;
  description: string;
}

interface DiagnosisSubmitResponse {
  success: boolean;
  data?: { session_id: number; cards?: IdeaCard[] };
  error?: { message: string };
}

/**
 * 선택 질문 4/4 (Q10 · 보유역량, 전체 진단의 마지막 화면). 슬롯: coreSkill.
 * 지금까지 diagnosisAnswers에 쌓인 답변 전체를 모아 여기서 한 번에
 * POST /api/diagnosis/submit로 제출한다.
 * 로그인이 필요하다(profile_id를 찾아야 저장 가능) - 비로그인이면 401 에러를
 * 그대로 안내 문구로 보여준다.
 */
function DiagnosisStep9() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [initialValue, setInitialValue] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [cards, setCards] = useState<IdeaCard[]>([]);

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.sido || !answers.sigungu || !answers.dong) {
      navigate("/diagnosis/5", { replace: true });
      return;
    }
    setInitialValue(answers.coreSkill ?? "");
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/8");
  const handleFinish = () => navigate("/home");

  const handleSubmit = async (value: string) => {
    if (submitting) return;
    const answers = saveDiagnosisAnswers({ coreSkill: value });
    const hasStoreDerived = answers.storeType === "offline" || answers.storeType === "booking";

    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE_URL}/api/diagnosis/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          origin: answers.origin || "problem",
          seed_interest: answers.seedInterest || "",
          problem_to_solve: answers.problemToSolve || "",
          solution_approach: answers.solutionApproach || "",
          has_store: hasStoreDerived,
          sido: answers.sido || "",
          sigungu: answers.sigungu || "",
          dong: answers.dong || "",
          target: answers.target || "",
          differentiator: answers.differentiator || "",
          revenue_model: answers.revenueModel || "",
          core_skill: value,
        }),
      });
      if (res.status === 401) {
        setError("로그인이 필요해요. 로그인 후 다시 시도해주세요.");
        return;
      }
      const data: DiagnosisSubmitResponse = await res.json();
      if (!data.success) {
        setError(data.error?.message || "제출에 실패했어요.");
        return;
      }
      setCards(data.data?.cards ?? []);
      setSubmitted(true);
      clearDiagnosisAnswers();
    } catch {
      setError("서버에 연결할 수 없습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!ready) return null;

  if (submitted) {
    return (
      <div className={`pageContainer ${styles.page}`}>
        <DiagnosisHeader onBack={handleFinish} pct="100%" stepLabel="완료" />
        <div className={styles.scrollArea}>
          <h1 className={styles.questionTitle}>사업 구체화가 끝났어요!</h1>
          <p className={styles.noticeText}>
            답변이 저장됐어요. 업종코드 매칭·분석 리포트 연결은 준비 중이라, 완성되면
            마이페이지에서 결과를 확인하실 수 있어요.
          </p>
          {cards.map((c, i) => (
            <div key={i} className={styles.resultCard}>
              <span className={styles.resultAxis}>{c.axis}</span>
              <span className={styles.resultTitle}>{c.title}</span>
              <span className={styles.resultDesc}>{c.description}</span>
            </div>
          ))}
        </div>
        <div className={styles.footer}>
          <button type="button" className={styles.nextButton} style={{ width: "100%" }} onClick={handleFinish}>
            홈으로
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="92%" stepLabel="선택 질문 · 4/4" />
      <DiagnosisTextQuestion
        topicBadge="Q10 · 보유역량"
        title="이 문제를 해결할 수 있는 본인만의 강점·경험이 있으신가요?"
        sub="자격증, 경력, 네트워크 등 구체적으로 작성해주세요"
        placeholder="예: 바리스타 자격증, 요식업 경력"
        initialValue={initialValue}
        required={false}
        buttonLabel={submitting ? "제출 중..." : "제출하기"}
        onSubmit={handleSubmit}
        onBack={handleBack}
        error={error}
      />
    </div>
  );
}

export default DiagnosisStep9;
