import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import industryStyles from "../../styles/diagnosisIndustryCode.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import { authHeaders } from "../../auth/session";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const POLL_INTERVAL_MS = 2000;
// [2026-09-12] 네트워크 오류(백엔드에 아예 닿지 않는 경우 등)일 때 예전엔 에러 표시 없이
// 계속 조용히 재시도해서 "무한 로딩"처럼 보이는 문제가 있었다(사용자 확인) - 10번(20초)
// 넘게 연속 실패하면 재시도를 멈추고 에러를 보여준다. 성공하면 카운터는 다시 0으로.
const MAX_NETWORK_RETRIES = 10;

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

interface DiagnosisSelectIndustryResponse {
  success: boolean;
  data?: { session_id: number; resolvedKsicCodes?: string[] };
  error?: { message: string };
}

/**
 * "질응답 내용 정리" 다음, "분석 리포트" 이전에 끼는 "업종코드 보여주기" 화면
 * (사용자 확인, 2026-09-12) - Q6(지역) 제출 시 POST /api/diagnosis/start가 이미
 * 확정해둔 업종코드 매칭 후보(sessionStorage)를 보여준다.
 *
 * [2026-09-12] 후보가 2개 이상이면 사용자가 하나를 확정(라디오 선택)해야만 "분석
 * 리포트 보러가기"가 가능하게 바꿈(사용자 확인) - 이유: 상권/기술창업 분석(밀집도,
 * 유사기업 수)은 후보 여러 개를 한꺼번에 넘기면 콤마로 합친 문자열 전체를 코드
 * 하나로 취급해 실제로는 아무 업체와도 안 맞는 버그가 있었다(backend/api/
 * diagnosis.py 모듈 상단 주석 참고) - 애초에 사용자가 하나로 확정하게 만들어서
 * 여러 개를 같이 넘길 일 자체를 없앤다. 후보가 1개 이하면 고를 게 없으니 선택
 * UI 없이 그 코드(또는 빈 값)로 바로 진행한다.
 *
 * [2026-09-12] 이 화면이 "분석 리포트 보러가기" 클릭 시점에 POST /{sessionId}/
 * select-industry(확정된 코드로 상권/기술창업 분석 시작)를 먼저 부르고, 그 응답을
 * 받은 뒤에야 GET /{sessionId}/report를 폴링한다 - 예전엔 6번(지역) 제출 시점에
 * 바로 분석이 시작됐는데, 이제는 사용자가 업종을 확정한 뒤에야 시작된다
 * (DiagnosisAnswerSummary.tsx는 더 이상 분석을 트리거하지 않음).
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
  const [sido, setSido] = useState("");
  const [sigungu, setSigungu] = useState("");
  const [dong, setDong] = useState("");
  const [seedInterest, setSeedInterest] = useState("");
  const [problemToSolve, setProblemToSolve] = useState("");
  const [solutionApproach, setSolutionApproach] = useState("");
  // [2026-09-12] 후보가 2개 이상일 때만 실제로 쓰이는 선택 상태 - 후보 1개 이하면
  // null로 두고 handleNext에서 ksicCodes[0]을 그대로 쓴다(선택 UI 자체가 없음).
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState("");
  // [2026-09-12] handleNext는 useEffect가 아니라 버튼 클릭 핸들러라 return값으로
  // cleanup을 걸 수 없다 - 폴링 도중 화면을 벗어나도 계속 도는 걸 막으려고 언마운트
  // 여부를 ref로 따로 들고 있는다.
  const unmountedRef = useRef(false);

  useEffect(() => {
    // [2026-09-13] 버그 수정 - 개발 모드 StrictMode가 마운트 직후 effect를
    // 한 번 껐다 켜보는 과정에서(cleanup 먼저 실행) unmountedRef.current가 true로
    // 굳어버려서, 분석이 다 끝나도 poll()이 "이미 언마운트됨"으로 착각해 navigate
    // 직전에 조용히 멈추는 문제가 있었다(사용자 확인 - "완료됐는데 페이지 이동 안 함").
    // 매 마운트마다 명시적으로 false로 되돌려서 StrictMode의 재실행 이후에도 정상값 유지.
    unmountedRef.current = false;
    const answers = getDiagnosisAnswers();
    if (!answers.sessionId) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setSessionId(answers.sessionId);
    setTrack(answers.track);
    setSido(answers.sido ?? "");
    setSigungu(answers.sigungu ?? "");
    setDong(answers.dong ?? "");
    setSeedInterest(answers.seedInterest ?? "");
    setProblemToSolve(answers.problemToSolve ?? "");
    setSolutionApproach(answers.solutionApproach ?? "");
    const codes = answers.resolvedKsicCodes ?? [];
    setKsicCodes(codes);
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

  const needsSelection = ksicCodes.length > 1;
  const handleBack = () => navigate("/diagnosis/summary");

  const handleNext = () => {
    if (checking || !sessionId) return;
    const codeToUse = needsSelection ? selectedCode : ksicCodes[0] ?? "";
    if (needsSelection && !codeToUse) return; // 버튼이 이미 disabled로 막지만 방어적으로 한 번 더

    setChecking(true);
    setCheckError("");
    let networkRetries = 0;
    // [2026-09-13] "ready: false"만 계속 오는 경우엔 재시도 횟수 제한이 아예 없었다
    // (네트워크 오류일 때만 세던 MAX_NETWORK_RETRIES와 별개) - 분석이 비정상적으로
    // 오래 걸리거나 응답이 캐시돼서 매번 같은 답만 오는 경우 등, 사용자 확인 없이
    // 무한 로딩처럼 보이는 사례가 실측됨. 최대 60회(2분)까지만 기다리고 그 이후엔
    // 에러로 안내한다.
    let notReadyRetries = 0;
    const MAX_NOT_READY_RETRIES = 60;

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/diagnosis/${sessionId}/report`, {
          headers: authHeaders(),
          cache: "no-store", // [2026-09-13] GET 폴링이 브라우저/중간 캐시에 걸려 오래된
          // "ready: false" 응답을 계속 재사용하는 경우를 막는다 - 서버는 이미
          // 완료됐는데 화면만 계속 도는 사례 실측됨(사용자 확인).
        });
        if (unmountedRef.current) return;
        networkRetries = 0; // 요청 자체는 갔다 왔으니(응답 성공/실패 무관) 네트워크는 살아있다고 봄
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
          notReadyRetries += 1;
          if (notReadyRetries >= MAX_NOT_READY_RETRIES) {
            setCheckError("분석이 예상보다 오래 걸리고 있어요. 잠시 후 다시 시도해주세요.");
            setChecking(false);
            return;
          }
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
        if (unmountedRef.current) return;
        networkRetries += 1;
        if (networkRetries >= MAX_NETWORK_RETRIES) {
          setCheckError("서버에 연결할 수 없어요. 네트워크 상태를 확인하고 다시 시도해주세요.");
          setChecking(false);
          return;
        }
        setTimeout(poll, POLL_INTERVAL_MS); // 네트워크 일시 오류 - 한도 내에서 계속 재시도
      }
    };

    const startAnalysis = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/diagnosis/${sessionId}/select-industry`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({
            ksic_code: codeToUse ?? "",
            has_store: track === "cafe",
            sido,
            sigungu,
            dong,
            seed_interest: seedInterest,
            problem_to_solve: problemToSolve,
            solution_approach: solutionApproach,
          }),
        });
        if (unmountedRef.current) return;
        if (res.status === 401) {
          setCheckError("로그인이 필요해요. 로그인 후 다시 시도해주세요.");
          setChecking(false);
          return;
        }
        const body: DiagnosisSelectIndustryResponse = await res.json();
        if (!body.success) {
          setCheckError(body.error?.message || "업종 확정에 실패했어요.");
          setChecking(false);
          return;
        }
        saveDiagnosisAnswers({ resolvedKsicCodes: body.data?.resolvedKsicCodes ?? (codeToUse ? [codeToUse] : []) });
        poll();
      } catch {
        if (!unmountedRef.current) {
          setCheckError("서버에 연결할 수 없습니다.");
          setChecking(false);
        }
      }
    };
    startAnalysis();
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="100%" stepLabel="AI 제안 · 업종코드 매칭" />
      <div className={styles.scrollArea}>
        <h1 className={industryStyles.title}>업종코드를 찾았어요</h1>
        <div className={industryStyles.anchorBox}>
          <span className={industryStyles.anchorText}>
            {needsSelection
              ? "물꼬가 찾은 후보 업종이 여러 개예요. 가장 가까운 업종 하나를 선택해주세요."
              : "방금 답변하신 문제인식·해결방식 등 PSST 내용을 물꼬가 종합해서, 가장 가까운 업종코드를 아래처럼 찾아드렸어요."}
          </span>
        </div>
        <p className={industryStyles.disclaimer}>이건 참고용 추천이며, 최종 등록 시 세무 전문가 확인을 권장합니다.</p>

        {ksicCodes.length > 0 ? (
          <div className={styles.cardList}>
            {ksicCodes.map((code, i) =>
              needsSelection ? (
                <button
                  key={code}
                  type="button"
                  className={industryStyles.matchCard}
                  onClick={() => setSelectedCode(code)}
                >
                  <span className={industryStyles.matchCardHead}>
                    <span className={industryStyles.matchCardTitle}>
                      {industryName || "업종 미확인"}
                    </span>
                    <span className={styles.radioDot}>
                      {selectedCode === code && <span className={styles.radioDotOn} />}
                    </span>
                  </span>
                  <span className={industryStyles.matchCodeText}>
                    업종코드 {code}
                    {i === 0 && industryConfidence ? ` · 신뢰도 ${industryConfidence}` : ""}
                  </span>
                </button>
              ) : (
                <div key={code} className={industryStyles.matchCard}>
                  <span className={industryStyles.matchCardHead}>
                    <span className={industryStyles.matchCardTitle}>
                      {industryName || "업종 미확인"}
                    </span>
                  </span>
                  <span className={industryStyles.matchCodeText}>
                    업종코드 {code}
                    {industryConfidence ? ` · 신뢰도 ${industryConfidence}` : ""}
                  </span>
                </div>
              ),
            )}
          </div>
        ) : (
          <div className={industryStyles.matchCard}>
            <span className={industryStyles.matchCodeText}>업종을 특정하지 못했어요.</span>
          </div>
        )}

        {needsSelection && !selectedCode && (
          <p className={styles.errorText}>업종을 하나 선택해야 다음으로 진행할 수 있어요.</p>
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
        <button
          type="button"
          className={styles.nextButton}
          disabled={checking || (needsSelection && !selectedCode)}
          onClick={handleNext}
        >
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
