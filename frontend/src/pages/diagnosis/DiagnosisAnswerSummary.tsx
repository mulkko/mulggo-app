import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import { authHeaders } from "../../auth/session";
import { getDiagnosisAnswers, saveDiagnosisAnswers, type Origin, type StoreType } from "./diagnosisAnswers";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const ORIGIN_LABEL: Record<Origin, string> = {
  problem: "① 불편했던 경험에서 (문제 해결형)",
  opportunity: "② 이런 게 있으면 좋겠다 (기회 추구형)",
};

const STORE_TYPE_LABEL: Record<StoreType, string> = {
  offline: "① 고객 방문형 오프라인 매장·공간",
  booking: "② 예약 방문형 서비스 공간",
  delivery: "③ 배달·제조 중심, 고객 방문 없음",
  online: "④ 온라인 판매·중개 플랫폼",
  digital: "⑤ 앱·소프트웨어·디지털 서비스",
};

interface IndustryMatch {
  state: string;
  name: string;
  confidence: string;
  question: string;
}

interface DiagnosisStartResponse {
  success: boolean;
  data?: {
    session_id: number;
    resolvedKsicCodes?: string[];
    industryMatch?: IndustryMatch | null;
    track?: "cafe" | "tech";
  };
  error?: { message: string };
}

/**
 * 6번(지역) 제출 직후 뜨는 "질응답 내용 정리" 화면 (사용자 확인) - 필수 질문 6개
 * 답변을 한눈에 보여준 뒤 "업종코드 보여주기"(DiagnosisIndustryResult) →
 * 분석 리포트(DiagnosisReport) 순으로 이어진다.
 *
 * [2026-09-12] 업종코드 매칭(POST /api/diagnosis/start) 트리거를 Q6(DiagnosisStep5)
 * 에서 여기로 옮김(사용자 확인) - Q1~Q6 답변을 먼저 요약으로 보여준 다음 "분석
 * 시작" 버튼을 눌러야 세션 생성 + 업종코드 매칭이 시작된다. 매칭(11~13초)이 끝나면
 * 바로 업종코드 결과 화면으로 넘어가고, 상권/기술창업 분석(추가 7~9초)은 그 뒤로도
 * 백그라운드에서 계속 돈다 - "분석 리포트" 화면(DiagnosisReport)이 완료 여부를
 * 폴링해서 마저 보여준다(backend/api/diagnosis.py 상단 주석 참고, 이 뒷부분은
 * 그대로 유지).
 *
 * [2026-09-12] 카드 디자인은 emkim99님이 만든 DiagnosisPsstConfirm.tsx(같은 목적의
 * 별도 화면, 디자인 참고용으로만 남김)의 .cardList/.confirmCard를 그대로 가져다 씀
 * (사용자 확인 - 로직은 이 화면 그대로, 디자인만 emkim99님 걸로).
 */
function DiagnosisAnswerSummary() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [answers, setAnswers] = useState(getDiagnosisAnswers());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!submitting) return;
    setElapsedSeconds(0);
    const timer = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [submitting]);

  useEffect(() => {
    const a = getDiagnosisAnswers();
    if (!a.sido || !a.sigungu || !a.dong) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setAnswers(a);
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/6");

  const handleNext = async () => {
    if (submitting) return;
    const hasStore = answers.storeType === "offline" || answers.storeType === "booking";

    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE_URL}/api/diagnosis/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          origin: answers.origin || "problem",
          seed_interest: answers.seedInterest || "",
          problem_to_solve: answers.problemToSolve || "",
          solution_approach: answers.solutionApproach || "",
          has_store: hasStore,
          sido: answers.sido,
          sigungu: answers.sigungu,
          dong: answers.dong,
        }),
      });
      if (res.status === 401) {
        setError("로그인이 필요해요. 로그인 후 다시 시도해주세요.");
        return;
      }
      const data: DiagnosisStartResponse = await res.json();
      if (!data.success || !data.data) {
        setError(data.error?.message || "진단 시작에 실패했어요.");
        return;
      }
      const match = data.data.industryMatch;
      saveDiagnosisAnswers({
        sessionId: data.data.session_id,
        resolvedKsicCodes: data.data.resolvedKsicCodes ?? [],
        industryMatchName: match?.name,
        industryMatchState: match?.state,
        industryMatchConfidence: match?.confidence,
        track: data.data.track,
      });
      navigate("/diagnosis/industry-result");
    } catch {
      setError("서버에 연결할 수 없습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!ready) return null;

  const origin = answers.origin ?? "problem";
  const region = [answers.sido, answers.sigungu, answers.dong].filter(Boolean).join(" ");

  const rows: { label: string; value: string }[] = [
    { label: "Q1 · 사업 아이템", value: answers.seedInterest ?? "" },
    { label: "Q2 · 출발점", value: ORIGIN_LABEL[origin] },
    { label: "Q3 · 문제 정의", value: answers.problemToSolve ?? "" },
    { label: "Q4 · 해결 방식", value: answers.solutionApproach ?? "" },
    { label: "Q5 · 매장 운영 형태", value: answers.storeType ? STORE_TYPE_LABEL[answers.storeType] : "" },
    { label: "Q6 · 지역·규모", value: region },
  ];

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="100%" stepLabel="AI 제안 · 답변 정리" />
      <div className={styles.scrollArea}>
        <h1 className={styles.questionTitle}>지금까지 답변한 내용이에요</h1>
        <p className={styles.questionSub}>이 내용을 바탕으로 업종코드를 매칭하고 분석 리포트를 준비했어요.</p>
        <div className={styles.cardList}>
          {rows.map((row) => (
            <div key={row.label} className={styles.confirmCard}>
              <span className={styles.confirmCardLabel}>{row.label}</span>
              <span className={styles.confirmCardValue}>{row.value || "-"}</span>
            </div>
          ))}
        </div>
        {error && <p className={styles.errorText}>{error}</p>}
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={handleBack}>
          이전
        </button>
        <button type="button" className={styles.nextButton} disabled={submitting} onClick={handleNext}>
          {submitting ? "분석 시작 중..." : "업종코드 확인하기 →"}
        </button>
      </div>
      {submitting && (
        <div className={styles.loadingOverlay}>
          <div className={styles.loadingBox} role="status" aria-live="polite">
            <div className={styles.spinner} />
            <p className={styles.loadingText}>업종코드를 분석하고 있어요... ({elapsedSeconds}초 경과)</p>
            <p className={styles.loadingHint}>상권·기술창업 분석은 다음 화면에서 마저 준비할게요</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default DiagnosisAnswerSummary;
