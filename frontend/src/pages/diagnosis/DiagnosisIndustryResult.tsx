import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import industryStyles from "../../styles/diagnosisIndustryCode.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import { authHeaders } from "../../auth/session";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";
import BottomNav from "../../components/BottomNav/BottomNav";

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
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    analysisByCode?: Record<string, any>;
    targetAnchor?: string | null;
    differentiatorAnchor?: string | null;
  };
  error?: { message: string };
}

/**
 * "질응답 내용 정리" 다음, "분석 리포트" 이전에 끼는 "업종코드 보여주기" 화면
 * (사용자 확인, 2026-09-12) - Q6(지역) 제출 시 POST /api/diagnosis/start가 이미
 * 확정해둔 업종코드 매칭 후보(sessionStorage)를 보여준다.
 *
 * [2026-09-13] 후보가 여러 개여도 하나를 강제로 고르게 하지 않는다(사용자 확인,
 * 이전엔 라디오 선택 강제 + POST /{id}/select-industry로 확정한 코드만 분석했음) -
 * POST /start 시점에 후보 전부(최대 3개)를 백엔드가 각자 백그라운드로 분석하기
 * 시작하므로, 이 화면은 후보를 읽기 전용으로 보여주기만 하고 "다음"을 누르면 바로
 * GET /{id}/report를 폴링해서 전부 끝나길 기다렸다가 분석 리포트 화면으로 넘어간다
 * (분석 리포트 화면 상단 셀렉박스가 후보별 결과를 보여줌 - DiagnosisReport.tsx 참고).
 */
function DiagnosisIndustryResult() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [ksicCodes, setKsicCodes] = useState<string[]>([]);
  const [industryName, setIndustryName] = useState("");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [track, setTrack] = useState<"cafe" | "tech" | undefined>(undefined);
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
    const codes = answers.resolvedKsicCodes ?? [];
    setKsicCodes(codes);
    setIndustryName(answers.industryMatchName ?? "");
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
          analysisByCode: body.data.analysisByCode,
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
    poll();
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="100%" stepLabel="업종코드 매칭" hideProgress />
      <div className={styles.scrollArea}>
        <h1 className={industryStyles.title}>업종코드를 찾았어요</h1>
        <div className={industryStyles.anchorBox}>
          <span className={industryStyles.anchorText}>
            {ksicCodes.length > 1
              ? "물꼬가 찾은 후보 업종이 여러 개예요. 전부 분석해서 다음 화면 상단에서 골라볼 수 있어요."
              : "방금 답변하신 문제인식·해결방식 등 PSST 내용을 물꼬가 종합해서, 가장 가까운 업종코드를 아래처럼 찾아드렸어요."}
          </span>
        </div>
        <p className={industryStyles.disclaimer}>이건 참고용 추천이며, 최종 등록 시 세무 전문가 확인을 권장합니다.</p>

        {ksicCodes.length > 0 ? (
          <div className={styles.cardList}>
            {ksicCodes.map((code) => (
              <div key={code} className={industryStyles.matchCard}>
                <span className={industryStyles.matchCardHead}>
                  <span className={industryStyles.matchCardTitle}>{industryName || "업종 미확인"}</span>
                </span>
                <span className={industryStyles.matchCodeText}>업종코드 {code}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className={industryStyles.matchCard}>
            <span className={industryStyles.matchCodeText}>업종을 특정하지 못했어요.</span>
          </div>
        )}

        {/* [2026-09-14, 사용자 확인] 프로토타입("12 업종코드 매칭" 화면) 원본 대조 -
            이 배너는 원래 백엔드 매칭 상태(industryState) 문구가 아니라, 어느
            트랙(카페형/기술창업형)으로 분류됐는지 안내하는 용도였다. 색은 프로토타입
            원본(#DFF3EF/#0F6E62) 그대로가 아니라 스타일가이드 토큰(--color-teal-mist/
            --color-teal-green, 값 완전히 동일)으로 매핑했다. */}
        {track && (
          <div className={industryStyles.stateBanner}>
            <span className={industryStyles.stateBannerTitle}>
              {track === "cafe" ? "상권분석형으로 분류됐어요" : "기술창업형으로 분류됐어요"}
            </span>
            <span className={industryStyles.stateBannerDesc}>
              {track === "cafe"
                ? "오프라인 매장 기반 사업이라 상권 데이터 분석으로 이동합니다"
                : "온라인·기술 기반 사업이라 특허·투자 동향 분석으로 이동합니다"}
            </span>
          </div>
        )}
        {checkError && <p className={styles.errorText}>{checkError}</p>}
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={handleBack}>
          이전
        </button>
        <button type="button" className={styles.nextButton} disabled={checking} onClick={handleNext}>
          {checking ? (
            "분석 확인 중..."
          ) : (
            <>
              분석 리포트 보러가기
              <svg
                className={styles.nextButtonIcon}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M8 5l8 7-8 7" />
              </svg>
            </>
          )}
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

      <BottomNav active="idea" />
    </div>
  );
}

export default DiagnosisIndustryResult;
