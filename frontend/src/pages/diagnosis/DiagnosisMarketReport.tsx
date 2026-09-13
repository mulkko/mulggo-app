import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosisMarketReport.module.css";
import diagnosisStyles from "../../styles/diagnosis.module.css";
import { getDiagnosisAnswers } from "./diagnosisAnswers";
import ChatFab from "../../components/ChatFab/ChatFab";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface MarketReportData {
  region: { sido: string; sigungu: string; dong: string };
  resident_population: { dong_code: string; region_name: string; resident_population: number | null };
  footfall: {
    data_type: string | null;
    region_level: string | null;
    region_name: string;
    raw_value: number | null;
    score: number | null;
    basis: string | null;
  };
  total_nearby_count: number;
  industry_mix: Array<{ 업종명: string; 업체수: number }>;
  density: unknown | null;
}

interface ApiError {
  message: string;
  code: string;
}

/**
 * 13. 상권분석 리포트. 순서: Q6(지역·규모) → 11(PSST 확정) → 12(업종코드 매칭) → 이 화면
 * → Q7~Q10. 이전 화면에 대한 가정은 "sido/sigungu/dong이 diagnosisAnswers에 이미
 * 채워져 있다"는 것 하나뿐이다 (Q7~Q10이 쓰는 가드 패턴과 동일) - 그래서 슬롯이
 * 없을 때의 가드 리다이렉트는 그대로 /diagnosis/6(Q6)으로 보낸다.
 *
 * ksic_code(업종코드)는 아직 없는 시점이라 GET /analysis/market에 안 넘긴다 - 그래서
 * "반경 500m 동일 업종"/"매칭 지원사업 수"/밀집도 히트맵은 채울 데이터가 없는 게
 * 버그가 아니라 의도된 빈 상태다.
 */
function DiagnosisMarketReport() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [dong, setDong] = useState("");
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<MarketReportData | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [showFootfallTip, setShowFootfallTip] = useState(false);

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.sido || !answers.sigungu || !answers.dong) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setDong(answers.dong);
    setReady(true);

    const params = new URLSearchParams({
      sido: answers.sido,
      sigungu: answers.sigungu,
      dong: answers.dong,
    });
    setLoading(true);
    fetch(`${API_BASE_URL}/analysis/market?${params.toString()}`)
      .then((res) => res.json())
      .then((body: { success: boolean; data?: MarketReportData; error?: ApiError }) => {
        if (body.success && body.data) setData(body.data);
        else setError(body.error ?? { message: "상권분석 리포트를 불러오지 못했어요.", code: "UNKNOWN" });
      })
      .catch(() => setError({ message: "상권분석 리포트를 불러오지 못했어요.", code: "NETWORK_ERROR" }))
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/industry-code");
  const handleNext = () => navigate("/diagnosis/7");

  if (!ready) return null;

  const maxIndustryCount = Math.max(0, ...(data?.industry_mix ?? []).map((item) => item.업체수));

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M16 5l-8 7 8 7" />
            </svg>
          </button>
          <span className={styles.headerTitle}>상권분석 리포트</span>
        </div>
      </header>

      <ChatFab variant="default" />

      {loading && (
        <div className={styles.stateArea}>
          <div className={styles.spinner} aria-hidden="true" />
          <p className={styles.stateText}>상권 데이터를 불러오는 중...</p>
        </div>
      )}

      {!loading && error && (
        <div className={styles.stateArea}>
          <p className={styles.stateText}>{error.message}</p>
          <button type="button" className={styles.stateBackButton} onClick={handleBack}>
            이전으로
          </button>
        </div>
      )}

      {!loading && !error && data && (
        <>
          <div className={styles.scrollArea}>
            <h1 className={styles.regionTitle}>{dong} 주변 상권 동향</h1>

            <div className={styles.statGrid}>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>반경 500m 동일 업종</span>
                <span className={styles.statValueEmpty}>업종코드 확인 후 표시돼요</span>
              </div>

              <div className={styles.statCard}>
                <button
                  type="button"
                  className={styles.infoButton}
                  onClick={() => setShowFootfallTip((prev) => !prev)}
                  aria-label="생활인구지수 설명"
                  aria-pressed={showFootfallTip}
                >
                  ?
                </button>
                {showFootfallTip && (
                  <div className={styles.infoTooltip}>
                    {data.footfall.basis ?? "비교할 생활/유동인구 데이터가 없어요."}
                  </div>
                )}
                <span className={styles.statLabel}>생활인구지수</span>
                {data.footfall.score !== null ? (
                  <span className={`${styles.statValue} ${styles.statValueAccent}`}>{data.footfall.score}</span>
                ) : (
                  <span className={styles.statValueEmpty}>-</span>
                )}
              </div>

              <div className={styles.statCard}>
                <span className={styles.statLabel}>상주인구수</span>
                <span className={styles.statValue}>
                  {data.resident_population.resident_population !== null
                    ? `${data.resident_population.resident_population.toLocaleString()}명`
                    : "-"}
                </span>
              </div>

              <div className={`${styles.statCard} ${styles.statCardHighlight}`}>
                <span className={styles.statLabel}>매칭 지원사업 수</span>
                <span className={styles.statValueEmpty}>업종코드 매칭 후 표시돼요</span>
              </div>
            </div>

            <section className={styles.sectionCard}>
              <h2 className={styles.sectionTitle}>동일 행정동 내 상위 업종 분포</h2>
              {data.industry_mix.length > 0 ? (
                data.industry_mix.map((item) => (
                  <div key={item.업종명} className={styles.barRow}>
                    <span className={styles.barLabel}>{item.업종명}</span>
                    <span className={styles.barTrack}>
                      <span
                        className={`${styles.barFill} ${item.업체수 === maxIndustryCount ? styles.barFillMax : ""}`}
                        style={{ width: maxIndustryCount > 0 ? `${(item.업체수 / maxIndustryCount) * 100}%` : "0%" }}
                      />
                    </span>
                    <span className={styles.barCount}>{item.업체수}</span>
                  </div>
                ))
              ) : (
                <p className={styles.emptyText}>이 지역의 업종분포 데이터가 없어요.</p>
              )}
            </section>

            <section className={styles.sectionCard}>
              <h2 className={styles.sectionTitle}>동일업종 밀집도</h2>
              <p className={styles.emptyText}>업종코드 확인 후 표시돼요.</p>
            </section>
          </div>

          <div className={diagnosisStyles.bottom}>
            <button type="button" className={diagnosisStyles.prevButton} onClick={handleBack}>
              이전
            </button>
            <button type="button" className={diagnosisStyles.nextButton} onClick={handleNext}>
              다음 →
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default DiagnosisMarketReport;
