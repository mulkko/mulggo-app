import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosisIndustryCode.module.css";
import diagnosisStyles from "../../styles/diagnosis.module.css";
import marketReportStyles from "../../styles/diagnosisMarketReport.module.css";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface CodeOption {
  code: string;
  name: string;
}

interface IndustryCodeData {
  state: "추천" | "확인필요" | "정보부족" | string;
  question: string;
  primary: CodeOption;
  alternatives: CodeOption[];
  additional: CodeOption[];
}

interface ApiError {
  message: string;
  code: string;
}

/**
 * 12. 업종코드 매칭. backend/ml/industry_code_matching(다른 세션이 완성한 별도 모듈)을
 * 감싼 POST /api/industry-code 결과를 보여준다. LLM 호출 포함 8~25초 걸릴 수 있어
 * 로딩 스피너 + 안내문구를 꼭 보여준다. state가 "확인필요"/"정보부족"이어도 에러가
 * 아니라 정상 응답이라(백엔드가 success:true로 내려줌) 카드 리스트는 그대로 보여주고
 * 위에 안내 배너만 얹는다.
 *
 * 프로토타입엔 "기술창업형으로 분류됐어요" 배너 + 분기(14. 기술창업분석으로 이동)가
 * 있지만 14번 화면이 아직 없어서, 이번엔 분류 결과와 무관하게 "다음"은 항상
 * 13(상권분석 리포트)로 보낸다 (사용자 확인, 2026-09-11).
 */
function DiagnosisIndustryCode() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<IndustryCodeData | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [selectedCode, setSelectedCode] = useState("");

  const runMatch = useCallback(() => {
    const answers = getDiagnosisAnswers();
    const region = [answers.sido, answers.sigungu, answers.dong].filter(Boolean).join(" ");
    const hasStore = answers.storeType === "offline" || answers.storeType === "booking";

    setLoading(true);
    setError(null);
    fetch(`${API_BASE_URL}/api/industry-code`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        seed_interest: answers.seedInterest || "",
        problem_to_solve: answers.problemToSolve || "",
        solution_approach: answers.solutionApproach || "",
        has_store: hasStore,
        region,
      }),
    })
      .then((res) => res.json())
      .then((body: { success: boolean; data?: IndustryCodeData; error?: ApiError }) => {
        if (body.success && body.data) {
          setData(body.data);
          setSelectedCode(body.data.primary.code);
        } else {
          setError(body.error ?? { message: "업종코드를 찾지 못했어요.", code: "UNKNOWN" });
        }
      })
      .catch(() => setError({ message: "업종코드를 찾지 못했어요. 네트워크를 확인해주세요.", code: "NETWORK_ERROR" }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.sido || !answers.sigungu || !answers.dong) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setReady(true);
    runMatch();
  }, [navigate, runMatch]);

  const handleBack = () => navigate("/diagnosis/psst-confirm");

  const codeOptions: CodeOption[] = data ? [data.primary, ...data.alternatives] : [];

  const handleNext = () => {
    const picked = codeOptions.find((c) => c.code === selectedCode) ?? data?.primary;
    if (picked) saveDiagnosisAnswers({ ksicCode: picked.code, ksicName: picked.name });
    navigate("/diagnosis/market-report");
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M16 5l-8 7 8 7" />
          </svg>
        </button>
        <span className={styles.resultLabel}>매칭 결과</span>
      </header>

      {loading && (
        <div className={marketReportStyles.stateArea}>
          <div className={marketReportStyles.spinner} aria-hidden="true" />
          <p className={marketReportStyles.stateText}>업종코드를 찾는 중이에요, 최대 30초 정도 걸려요</p>
        </div>
      )}

      {!loading && error && (
        <div className={marketReportStyles.stateArea}>
          <p className={marketReportStyles.stateText}>{error.message}</p>
          <button type="button" className={marketReportStyles.stateBackButton} onClick={runMatch}>
            다시 시도
          </button>
        </div>
      )}

      {!loading && !error && data && (
        <>
          <div className={styles.scrollArea}>
            <h1 className={styles.title}>업종코드를 찾았어요</h1>
            <div className={diagnosisStyles.qAnchor}>
              <span className={diagnosisStyles.qAnchorText}>
                방금 답변하신 문제인식·해결방식 등 PSST 내용을 물꼬가 종합해서, 가장 가까운 업종코드를 아래처럼 찾아드렸어요.
              </span>
            </div>
            <p className={styles.disclaimer}>이건 참고용 추천이며, 최종 등록 시 세무 전문가 확인을 권장합니다.</p>

            {data.state !== "추천" && data.question && <div className={styles.stateBanner}>{data.question}</div>}

            <div className={diagnosisStyles.cardList}>
              {codeOptions.map((opt) => (
                <button
                  key={opt.code}
                  type="button"
                  className={diagnosisStyles.radioCard}
                  onClick={() => setSelectedCode(opt.code)}
                >
                  <span className={diagnosisStyles.radioCardHead}>
                    <span className={diagnosisStyles.radioCardTitle}>{opt.name}</span>
                    <span className={styles.codeMeta}>업종코드 {opt.code}</span>
                  </span>
                  <span className={diagnosisStyles.radioDot}>
                    {selectedCode === opt.code && <span className={diagnosisStyles.radioDotOn} />}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className={diagnosisStyles.bottom}>
            <button type="button" className={diagnosisStyles.prevButton} onClick={handleBack}>
              이전
            </button>
            <button type="button" className={diagnosisStyles.nextButton} onClick={handleNext}>
              분석 리포트 보러가기 →
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default DiagnosisIndustryCode;
