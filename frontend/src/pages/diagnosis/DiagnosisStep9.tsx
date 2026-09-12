import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import DiagnosisReportSummary, { type IdeaCard } from "./DiagnosisReportSummary";
import { authHeaders } from "../../auth/session";
import { clearDiagnosisAnswers, getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface DiagnosisFinishResponse {
  success: boolean;
  data?: { session_id: number; cards?: IdeaCard[]; resolvedKsicCodes?: string[] };
  error?: { message: string };
}

/**
 * 선택 질문 4/4 (Q10 · 보유역량, 전체 진단의 마지막 화면). 슬롯: coreSkill.
 * 단계별 즉시저장(backend/api/diagnosis.py 상단 주석 참고) 구조라, 세션은 5번에서 이미
 * 만들어져 있다 - 여기선 POST /api/diagnosis/{sessionId}/finish로 보유역량과 나머지
 * 선택 질문(타깃/차별점/수익모델, DB엔 안 남고 아이디어 카드 생성 재료로만 씀)을
 * 같이 보내 마무리한다.
 * 로그인이 필요하다(세션 소유자 확인) - 비로그인이면 401 에러를 그대로 안내 문구로
 * 보여준다.
 *
 * [2026-09-12] 제출 완료 화면은 DiagnosisReportSummary(13-1/14-2 리포트 파트2,
 * /dev/report-summary-preview에서 목업으로 미리 확인 가능했던 컴포넌트)를 그대로
 * 씀 - 타깃/차별점/수익모델/보유역량 요약 카드 + AI 아이디어 카드. 백엔드 응답의
 * resolvedKsicCodes로 "지원사업 매칭 보기" 버튼이 /matching?ksic=...&region=...로
 * 바로 이어지게 backPath/matchPath를 넘긴다(사용자 확인 - 로직/데이터 연결만 하고
 * 디자인은 그대로).
 */
function DiagnosisStep9() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [initialValue, setInitialValue] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [cards, setCards] = useState<IdeaCard[]>([]);
  const [summary, setSummary] = useState({ target: "", differentiator: "", revenueModel: "", coreSkill: "" });
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [variant, setVariant] = useState<"market" | "tech">("market");
  const [ksicQuery, setKsicQuery] = useState("");
  const [sido, setSido] = useState("");

  useEffect(() => {
    if (!submitting) return;
    setElapsedSeconds(0);
    const timer = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [submitting]);

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.sido || !answers.sigungu || !answers.dong || !answers.sessionId) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setSessionId(answers.sessionId);
    setInitialValue(answers.coreSkill ?? "");
    setSido(answers.sido);
    setVariant(answers.track === "tech" ? "tech" : "market");
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/9");

  const handleSubmit = async (value: string) => {
    if (submitting || !sessionId) return;
    const answers = saveDiagnosisAnswers({ coreSkill: value });

    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE_URL}/api/diagnosis/${sessionId}/finish`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
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
      const data: DiagnosisFinishResponse = await res.json();
      if (!data.success) {
        setError(data.error?.message || "제출에 실패했어요.");
        return;
      }
      setCards(data.data?.cards ?? []);
      setKsicQuery((data.data?.resolvedKsicCodes ?? []).join(","));
      setSummary({
        target: answers.target || "",
        differentiator: answers.differentiator || "",
        revenueModel: answers.revenueModel || "",
        coreSkill: value,
      });
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
      <DiagnosisReportSummary
        variant={variant}
        target={summary.target}
        differentiator={summary.differentiator}
        revenueModel={summary.revenueModel}
        coreSkill={summary.coreSkill}
        cards={cards}
        backPath="/diagnosis/report"
        matchPath={`/matching?ksic=${encodeURIComponent(ksicQuery)}&region=${encodeURIComponent(sido)}`}
      />
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
      {submitting && (
        <div className={styles.loadingOverlay}>
          <div className={styles.loadingBox} role="status" aria-live="polite">
            <div className={styles.spinner} />
            <p className={styles.loadingText}>사업 구체화 결과를 정리하고 있어요... ({elapsedSeconds}초 경과)</p>
            <p className={styles.loadingHint}>아이디어 카드를 만드는 중이라 시간이 걸릴 수 있어요</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default DiagnosisStep9;
