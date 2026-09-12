import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import industryStyles from "../../styles/diagnosisIndustryCode.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import { authHeaders } from "../../auth/session";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const POLL_INTERVAL_MS = 2000;

interface DiagnosisReportResponse {
  success: boolean;
  data?: {
    ready: boolean;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    marketAnalysis?: any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    techAnalysis?: any;
    targetAnchor?: string | null;
    differentiatorAnchor?: string | null;
  };
  error?: { message: string };
}

/**
 * "질응답 내용 정리" 다음, "분석 리포트" 이전에 끼는 "업종코드 보여주기" 화면
 * (사용자 확인, 2026-09-12) - Q6(지역) 제출 시 POST /api/diagnosis/start가 이미
 * 확정해둔 업종코드 매칭 결과(sessionStorage)를 그대로 보여주기만 하는 순수 표시
 * 화면이다. 선택(라디오) 기능은 없음 - 지금 매칭 코드는 최대 3개까지 나오는 "대체
 * 가능한 후보" 개념이라 사용자가 그중 하나를 고를 필요가 없다고 판단(사용자 확인).
 *
 * emkim99님 DiagnosisIndustryCode.tsx(디자인 참고용, /diagnosis/industry-code-test로
 * 목업 확인 가능)는 후보마다 이름이 각각 붙은 라디오카드 리스트인데, 지금 백엔드
 * (/api/diagnosis/start)는 1순위 업종명 1개 + KSIC코드 목록(코드만, 이름 없음)만
 * 내려준다 - 후보별 개별 이름을 보여주려면 백엔드가 candidates 전체를 반환하도록
 * 바꿔야 해서 이번 범위 밖(사용자 확인, "단순 표시" 방식으로 결정) - 그래서 카드마다
 * 이름은 동일하게, 코드만 다르게 표시한다.
 *
 * [2026-09-12] "분석 리포트 보러가기" 버튼의 대기 위치를 여기로 옮김(사용자 확인) -
 * 예전엔 눌리자마자 /diagnosis/report로 넘어가고 그 화면에서 폴링하며 기다렸는데,
 * 이제는 여기서 GET /api/diagnosis/{sessionId}/report를 폴링하다가 준비된 뒤에야
 * 화면을 넘긴다(백그라운드 상권/기술창업 분석 완료 대기 - backend/api/diagnosis.py
 * 상단 주석 참고). DiagnosisReport.tsx의 폴링 로직은 그대로 남겨뒀다 - 도착 시점엔
 * 이미 끝나있어서 사실상 안전망 역할만 한다(직접 URL 접근 등 예외 상황 대비).
 */
function DiagnosisIndustryResult() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [ksicCodes, setKsicCodes] = useState<string[]>([]);
  const [industryName, setIndustryName] = useState("");
  const [industryState, setIndustryState] = useState("");
  const [industryConfidence, setIndustryConfidence] = useState("");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [track, setTrack] = useState<"cafe" | "tech" | undefined>(undefined);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState("");
  // [2026-09-12] handleNext는 useEffect가 아니라 버튼 클릭 핸들러라 return값으로
  // cleanup을 걸 수 없다 - 폴링 도중 화면을 벗어나도 계속 도는 걸 막으려고 언마운트
  // 여부를 ref로 따로 들고 있는다.
  const unmountedRef = useRef(false);

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.sessionId) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setSessionId(answers.sessionId);
    setTrack(answers.track);
    setKsicCodes(answers.resolvedKsicCodes ?? []);
    setIndustryName(answers.industryMatchName ?? "");
    setIndustryState(answers.industryMatchState ?? "");
    setIndustryConfidence(answers.industryMatchConfidence ?? "");
    setReady(true);
  }, [navigate]);

  useEffect(() => {
    return () => {
      unmountedRef.current = true;
    };
  }, []);

  const handleBack = () => navigate("/diagnosis/summary");

  const handleNext = () => {
    if (checking || !sessionId) return;
    setChecking(true);
    setCheckError("");

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/diagnosis/${sessionId}/report`, {
          headers: authHeaders(),
        });
        if (unmountedRef.current) return;
        if (res.status === 401) {
          setCheckError("로그인이 필요해요. 로그인 후 다시 시도해주세요.");
          setChecking(false);
          return;
        }
        const body: DiagnosisReportResponse = await res.json();
        if (!body.success || !body.data) {
          setCheckError(body.error?.message || "분석 리포트를 불러오지 못했어요.");
          setChecking(false);
          return;
        }
        if (!body.data.ready) {
          setTimeout(poll, POLL_INTERVAL_MS);
          return;
        }
        saveDiagnosisAnswers({
          marketAnalysis: body.data.marketAnalysis,
          techAnalysis: body.data.techAnalysis,
          targetAnchor: body.data.targetAnchor ?? undefined,
          differentiatorAnchor: body.data.differentiatorAnchor ?? undefined,
        });
        navigate("/diagnosis/report");
      } catch {
        if (!unmountedRef.current) setTimeout(poll, POLL_INTERVAL_MS); // 네트워크 일시 오류 - 계속 재시도
      }
    };
    poll();
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="100%" stepLabel="AI 제안 · 업종코드 매칭" />
      <div className={styles.scrollArea}>
        <h1 className={industryStyles.title}>업종코드를 찾았어요</h1>
        <div className={styles.qAnchor}>
          <span className={styles.qAnchorText}>
            방금 답변하신 문제인식·해결방식 등 PSST 내용을 물꼬가 종합해서, 가장 가까운 업종코드를 아래처럼 찾아드렸어요.
          </span>
        </div>
        <p className={industryStyles.disclaimer}>이건 참고용 추천이며, 최종 등록 시 세무 전문가 확인을 권장합니다.</p>

        {ksicCodes.length > 0 ? (
          <div className={styles.cardList}>
            {ksicCodes.map((code, i) => (
              <div key={code} className={styles.resultCard}>
                <span className={styles.resultAxis}>{i === 0 ? "1순위" : `대안 ${i}`}</span>
                <span className={styles.resultTitle}>🏷 {industryName || "업종 미확인"}</span>
                <span className={styles.resultDesc}>
                  업종코드 {code}
                  {i === 0 && industryConfidence ? ` · 신뢰도 ${industryConfidence}` : ""}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.resultCard}>
            <span className={styles.resultDesc}>업종을 특정하지 못했어요.</span>
          </div>
        )}

        {industryState && industryState !== "추천" && (
          <div className={industryStyles.stateBanner}>업종 판정 상태: {industryState}</div>
        )}
        {checkError && <p className={styles.errorText}>{checkError}</p>}
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={handleBack}>
          이전
        </button>
        <button type="button" className={styles.nextButton} disabled={checking} onClick={handleNext}>
          {checking ? "분석 확인 중..." : "분석 리포트 보러가기 →"}
        </button>
      </div>
      {checking && (
        <div className={styles.loadingOverlay}>
          <div className={styles.loadingBox} role="status" aria-live="polite">
            <div className={styles.spinner} />
            <p className={styles.loadingText}>
              {track === "cafe" ? "상권 리포트를 분석하고 있어요..." : "기술창업 리포트를 분석하고 있어요..."}
            </p>
            <p className={styles.loadingHint}>다 되면 자동으로 다음 화면으로 넘어가요</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default DiagnosisIndustryResult;
