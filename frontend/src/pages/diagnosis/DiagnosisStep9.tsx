import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import DiagnosisTextQuestion from "./DiagnosisTextQuestion";
import DiagnosisReportSummary, { type IdeaCard } from "./DiagnosisReportSummary";
import { authHeaders } from "../../auth/session";
import { clearDiagnosisAnswers, getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";
import BottomNav from "../../components/BottomNav/BottomNav";
import StageLoadingPopup from "../../components/StageLoadingPopup/StageLoadingPopup";
import ocrWriting from "../../assets/ocr_writing.png";
import ocrIdea from "../../assets/ocr_idea.png";

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
  const [finishReady, setFinishReady] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [cards, setCards] = useState<IdeaCard[]>([]);
  const [summary, setSummary] = useState({ target: "", differentiator: "", revenueModel: "", coreSkill: "" });
  const [variant, setVariant] = useState<"market" | "tech">("market");
  const [ksicQuery, setKsicQuery] = useState("");
  const [sido, setSido] = useState("");
  // handleSubmit 응답은 StageLoadingPopup 진행바가 100%까지 채워지는 걸 보여준 다음
  // (onDone) 반영한다 - 그 전까지는 화면 상태를 안 바꾸고 ref에만 들고 있는다.
  const finishResultRef = useRef<{
    cards: IdeaCard[];
    ksicQuery: string;
    summary: { target: string; differentiator: string; revenueModel: string; coreSkill: string };
  } | null>(null);

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    // dong은 기술창업형(오프라인 매장 아님)이면 비어있는 게 정상(DiagnosisStep5.tsx 참고).
    if (!answers.sido || !answers.sigungu || !answers.sessionId) {
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
    setFinishReady(false);
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
        setSubmitting(false);
        return;
      }
      const data: DiagnosisFinishResponse = await res.json();
      if (!data.success) {
        setError(data.error?.message || "제출에 실패했어요.");
        setSubmitting(false);
        return;
      }
      finishResultRef.current = {
        cards: data.data?.cards ?? [],
        ksicQuery: (data.data?.resolvedKsicCodes ?? []).join(","),
        summary: {
          target: answers.target || "",
          differentiator: answers.differentiator || "",
          revenueModel: answers.revenueModel || "",
          coreSkill: value,
        },
      };
      // StageLoadingPopup 진행바가 100%까지 채워지는 걸 보여준 다음(onDone) 결과 화면으로 전환한다.
      setFinishReady(true);
    } catch {
      setError("서버에 연결할 수 없습니다.");
      setSubmitting(false);
    }
  };

  const handleFinishDone = () => {
    const result = finishResultRef.current;
    if (result) {
      setCards(result.cards);
      setKsicQuery(result.ksicQuery);
      setSummary(result.summary);
      setSubmitted(true);
      clearDiagnosisAnswers();
    }
    setSubmitting(false);
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
        buttonLabel={submitting ? "제출 중..." : "제출하기"}
        onSubmit={handleSubmit}
        onBack={handleBack}
        error={error}
      />
      {submitting && (
        <StageLoadingPopup
          ready={finishReady}
          onDone={handleFinishDone}
          maxSeconds={60}
          hint="조금만 기다려 주세요! (최대 1분 소요)"
          stages={[
            { afterSeconds: 0, title: "사업구체화 결과를 정리하고 있어요.", image: ocrWriting },
            { afterSeconds: 45, title: "아이디어 카드를 만들고 있어요.", image: ocrIdea },
          ]}
        />
      )}

      <BottomNav active="idea" />
    </div>
  );
}

export default DiagnosisStep9;
