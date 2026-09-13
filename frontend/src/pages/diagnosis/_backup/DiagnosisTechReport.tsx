import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosisTechReport.module.css";
import diagnosisStyles from "../../../styles/diagnosis.module.css";
import { getDiagnosisAnswers } from "../diagnosisAnswers";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// TODO: 12번 업종코드 매칭 완성되면 diagnosisAnswers의 실제 ksic_code로 교체
const KSIC_CODE = "20112";
const KSIC_LABEL = "20112 · 바이오매스계 기초 화학물질 제조업";

const DENSITY_GRID_COLS = 6;
const DENSITY_GRID_ROWS = 3;

interface TypeDistributionItem {
  인증유형: string;
  건수: number;
  "비율(%)": number;
}

interface DensityCell {
  x: number;
  y: number;
  count: number;
  sigungu: string;
}

interface DensityGrid {
  grid_cols: number;
  grid_rows: number;
  cells: DensityCell[];
  total_sigungu_count: number;
  shown_sigungu_count: number;
  total_company_count: number;
  shown_company_count: number;
}

interface TechStartupData {
  similar_count: number;
  recent_investment_count: number;
  type_distribution: TypeDistributionItem[];
  density_grid: DensityGrid | null;
}

interface PatentData {
  keyword: string;
  actual: Record<string, number | null>;
  reliable_years: number[];
  forecast: Record<string, number>;
  backtest_results: unknown;
  mae: number | null;
}

interface ApiError {
  message: string;
  code: string;
}

const BAR_COLORS = [
  "var(--color-light-teal)",
  "var(--color-tab-active-icon)",
  "var(--color-stone-gray)",
  "var(--color-dot-inactive)",
];

function getBarColor(index: number): string {
  return BAR_COLORS[index] ?? BAR_COLORS[BAR_COLORS.length - 1];
}

function getDensityColor(count: number | null, maxCount: number): string {
  if (count === null) return "rgba(21, 50, 140, 0.05)";
  const ratio = maxCount > 0 ? count / maxCount : 0;
  return `rgba(21, 50, 140, ${(0.1 + ratio * 0.7).toFixed(2)})`;
}

/**
 * 14. 기술창업분석 리포트. 목표 순서는 Q6 → 11(PSST 확정) → 12(업종코드 매칭) → 이 화면
 * → Q7이지만, 11·12가 아직 없어 이 화면은 독립적으로만 접근 가능하게 만든다(13번과
 * 동일 방침, 사용자 확인 2026-09-11). "이전"은 아직 없는 12번 라우트 이름만 미리
 * 맞춰두고(/diagnosis/industry-code), "다음"은 13번과 동일하게 Q7 라우트로 직접 이동한다.
 *
 * ksic_code는 12번이 없는 시점이라 하드코딩(KSIC_CODE) — 12번이 생기면 diagnosisAnswers의
 * 실제 값으로 교체.
 */
function DiagnosisTechReport() {
  const navigate = useNavigate();

  const [techLoading, setTechLoading] = useState(true);
  const [techData, setTechData] = useState<TechStartupData | null>(null);
  const [techError, setTechError] = useState<ApiError | null>(null);

  const [patentLoading, setPatentLoading] = useState(false);
  const [patentData, setPatentData] = useState<PatentData | null>(null);
  const [patentError, setPatentError] = useState<ApiError | null>(null);
  const [patentRequested, setPatentRequested] = useState(false);

  const answers = useMemo(() => getDiagnosisAnswers(), []);
  const canFetchPatent = Boolean(
    answers.seedInterest && answers.problemToSolve && answers.solutionApproach
  );

  const fetchTechStartup = () => {
    setTechLoading(true);
    setTechError(null);
    fetch(`${API_BASE_URL}/analysis/tech-startup?ksic_code=${encodeURIComponent(KSIC_CODE)}`)
      .then((res) => res.json())
      .then((body: { success: boolean; data?: TechStartupData; error?: ApiError }) => {
        if (body.success && body.data) setTechData(body.data);
        else setTechError(body.error ?? { message: "기술창업분석 리포트를 불러오지 못했어요.", code: "UNKNOWN" });
      })
      .catch(() => setTechError({ message: "기술창업분석 리포트를 불러오지 못했어요.", code: "NETWORK_ERROR" }))
      .finally(() => setTechLoading(false));
  };

  useEffect(() => {
    fetchTechStartup();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchPatentTrend = () => {
    setPatentRequested(true);
    setPatentLoading(true);
    setPatentError(null);
    const params = new URLSearchParams({
      seed_interest: answers.seedInterest ?? "",
      problem_to_solve: answers.problemToSolve ?? "",
      solution_approach: answers.solutionApproach ?? "",
    });
    fetch(`${API_BASE_URL}/analysis/patent-startup?${params.toString()}`)
      .then((res) => res.json())
      .then((body: { success: boolean; data?: PatentData; error?: ApiError }) => {
        if (body.success && body.data) setPatentData(body.data);
        else setPatentError(body.error ?? { message: "특허 동향을 불러오지 못했어요.", code: "UNKNOWN" });
      })
      .catch(() => setPatentError({ message: "특허 동향을 불러오지 못했어요.", code: "NETWORK_ERROR" }))
      .finally(() => setPatentLoading(false));
  };

  const handleBack = () => navigate("/diagnosis/industry-code");
  const handleNext = () => navigate("/diagnosis/7");

  const hasSimilarCompanies = (techData?.similar_count ?? 0) > 0;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M16 5l-8 7 8 7" />
            </svg>
          </button>
          <span className={styles.headerTitle}>기술창업분석 리포트</span>
        </div>
      </header>

      {techLoading && (
        <div className={styles.stateArea}>
          <div className={styles.spinner} aria-hidden="true" />
          <p className={styles.stateText}>기술창업 데이터를 불러오는 중...</p>
        </div>
      )}

      {!techLoading && techError && (
        <div className={styles.stateArea}>
          <p className={styles.stateText}>{techError.message}</p>
          <button type="button" className={styles.stateBackButton} onClick={fetchTechStartup}>
            다시 시도
          </button>
        </div>
      )}

      {!techLoading && !techError && techData && (
        <>
          <div className={styles.scrollArea}>
            <div className={styles.codeLabel}>{KSIC_LABEL}</div>
            <h1 className={styles.regionTitle}>업종 및 특허분석 지표</h1>

            <div className={styles.statGrid}>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>유사 벤처인증기업 수</span>
                <span className={styles.statValue}>{techData.similar_count.toLocaleString()}개</span>
              </div>

              <div className={styles.statCard}>
                <span className={styles.statLabel}>벤처투자형 인증 (1년)</span>
                <span className={styles.statValue}>{techData.recent_investment_count.toLocaleString()}건</span>
              </div>

              <div className={`${styles.statCard} ${styles.statCardHighlight}`}>
                <span className={styles.statLabel}>매칭 지원사업 수</span>
                <span className={styles.statValueEmpty}>준비 중이에요</span>
              </div>
            </div>

            {!hasSimilarCompanies && (
              <section className={styles.sectionCard}>
                <p className={styles.emptyText}>해당 업종의 유사 벤처기업 데이터가 없어요.</p>
              </section>
            )}

            {hasSimilarCompanies && (
              <section className={styles.sectionCard}>
                <h2 className={styles.sectionTitle}>유사 기업 인증유형 구성</h2>
                {techData.type_distribution.map((item, index) => (
                  <div key={item.인증유형} className={styles.barRow}>
                    <span className={styles.barLabel}>{item.인증유형}</span>
                    <span className={styles.barTrack}>
                      <span
                        className={styles.barFill}
                        style={{
                          width: `${item["비율(%)"]}%`,
                          background: getBarColor(index),
                        }}
                      />
                    </span>
                    <span className={styles.barCount}>{item["비율(%)"]}%</span>
                  </div>
                ))}
              </section>
            )}

            <section className={styles.sectionCard}>
              <h2 className={styles.sectionTitle}>관련분야 특허출원 추이 (KIPRIS)</h2>

              {!patentRequested && (
                <button type="button" className={styles.patentButton} onClick={fetchPatentTrend} disabled={!canFetchPatent}>
                  특허 동향 보기
                </button>
              )}
              {!patentRequested && !canFetchPatent && (
                <p className={styles.emptyText}>이전 진단 답변이 없어 특허 동향을 조회할 수 없어요.</p>
              )}

              {patentRequested && patentLoading && (
                <div className={styles.patentStateArea}>
                  <div className={styles.spinner} aria-hidden="true" />
                  <p className={styles.stateText}>조회 중... (최대 몇십 초 걸릴 수 있어요)</p>
                </div>
              )}

              {patentRequested && !patentLoading && patentError && (
                <div className={styles.patentStateArea}>
                  <p className={styles.stateText}>{patentError.message}</p>
                  <button type="button" className={styles.stateBackButton} onClick={fetchPatentTrend}>
                    다시 시도
                  </button>
                </div>
              )}

              {patentRequested && !patentLoading && !patentError && patentData && (
                <PatentChart data={patentData} />
              )}
            </section>

            {techData.density_grid && (
              <section className={styles.sectionCard}>
                <h2 className={styles.sectionTitle}>동종산업 밀집도</h2>
                <DensityGridView grid={techData.density_grid} />
              </section>
            )}

            <p className={styles.sourceText}>출처: 중기부 벤처기업명단·특허청 KIPRIS 기준 · 개별 성공 확률 아님</p>
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

function PatentChart({ data }: { data: PatentData }) {
  const years = Object.keys(data.actual)
    .map(Number)
    .sort((a, b) => a - b);
  const reliableSet = new Set(data.reliable_years);
  const forecastEntries = Object.entries(data.forecast);
  const forecastYear = forecastEntries.length > 0 ? Number(forecastEntries[0][0]) : null;
  const forecastValue = forecastEntries.length > 0 ? forecastEntries[0][1] : null;

  const actualPoints = years
    .map((year) => ({ year, value: data.actual[String(year)] }))
    .filter((p): p is { year: number; value: number } => p.value !== null);

  if (actualPoints.length === 0) {
    return <p className={styles.emptyText}>표시할 특허 출원 데이터가 없어요.</p>;
  }

  const allValues = actualPoints.map((p) => p.value).concat(forecastValue !== null ? [forecastValue] : []);
  const maxValue = Math.max(...allValues, 1);
  const minValue = Math.min(...allValues, 0);

  const step = 36;
  const paddingX = 22;
  const chartHeight = 110;
  const topPad = 22;
  const bottomPad = 6;

  const xForYear = (year: number) => paddingX + years.indexOf(year) * step;
  const yForValue = (value: number) => {
    if (maxValue === minValue) return chartHeight - bottomPad - (chartHeight - topPad - bottomPad) / 2;
    const ratio = (value - minValue) / (maxValue - minValue);
    return chartHeight - bottomPad - ratio * (chartHeight - topPad - bottomPad);
  };

  const lastActual = actualPoints[actualPoints.length - 1];
  const reliablePoints = actualPoints.filter((p) => reliableSet.has(p.year));
  const unreliablePoints = actualPoints.filter((p) => !reliableSet.has(p.year));

  const reliablePolyline = reliablePoints.map((p) => `${xForYear(p.year)},${yForValue(p.value)}`).join(" ");
  const unreliableChain = reliablePoints.length > 0 ? [reliablePoints[reliablePoints.length - 1], ...unreliablePoints] : unreliablePoints;
  const unreliablePolyline = unreliableChain.map((p) => `${xForYear(p.year)},${yForValue(p.value)}`).join(" ");

  const chartWidth = paddingX * 2 + Math.max(years.length - 1, 0) * step;
  const hasUnreliableYears = years.some((y) => !reliableSet.has(y));

  return (
    <div className={styles.patentChartWrap}>
      <div className={styles.patentChartScroll}>
        <svg
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          preserveAspectRatio="none"
          className={styles.patentSvg}
          style={{ width: `${Math.max(chartWidth, 280)}px` }}
        >
          {reliablePolyline && (
            <polyline points={reliablePolyline} fill="none" stroke="var(--color-light-teal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          )}
          {unreliablePolyline && unreliableChain.length > 1 && (
            <polyline points={unreliablePolyline} fill="none" stroke="var(--color-light-teal)" strokeWidth="2" strokeDasharray="4 3" strokeLinecap="round" strokeLinejoin="round" opacity="0.55" />
          )}
          {forecastYear !== null && forecastValue !== null && (
            <polyline
              points={`${xForYear(lastActual.year)},${yForValue(lastActual.value)} ${paddingX + years.length * step},${yForValue(forecastValue)}`}
              fill="none"
              stroke="var(--color-deep-navy)"
              strokeWidth="2"
              strokeDasharray="2 3"
              strokeLinecap="round"
            />
          )}

          {reliablePoints.map((p) => (
            <circle key={p.year} cx={xForYear(p.year)} cy={yForValue(p.value)} r="4" fill="var(--color-light-teal)" />
          ))}
          {unreliablePoints.map((p) => (
            <circle key={p.year} cx={xForYear(p.year)} cy={yForValue(p.value)} r="4" fill="var(--color-white)" stroke="var(--color-light-teal)" strokeWidth="2" />
          ))}
          {forecastYear !== null && forecastValue !== null && (
            <circle cx={paddingX + years.length * step} cy={yForValue(forecastValue)} r="4" fill="var(--color-white)" stroke="var(--color-deep-navy)" strokeWidth="2" />
          )}

          {actualPoints.map((p) => (
            <text key={`v-${p.year}`} x={xForYear(p.year)} y={yForValue(p.value) - 8} textAnchor="middle" fontSize="9" fontWeight="700" fill="var(--color-ink-charcoal)">
              {p.value}
            </text>
          ))}
          {forecastYear !== null && forecastValue !== null && (
            <text x={paddingX + years.length * step} y={yForValue(forecastValue) - 8} textAnchor="middle" fontSize="9" fontWeight="700" fill="var(--color-deep-navy)">
              예측:{forecastValue}
            </text>
          )}

          {years.map((year) => (
            <text
              key={`x-${year}`}
              x={xForYear(year)}
              y={chartHeight}
              textAnchor="end"
              fontSize="9"
              fill="var(--color-stone-gray)"
              transform={`rotate(-40 ${xForYear(year)} ${chartHeight})`}
            >
              {year}
              {!reliableSet.has(year) ? "*" : ""}
            </text>
          ))}
          {forecastYear !== null && (
            <text
              x={paddingX + years.length * step}
              y={chartHeight}
              textAnchor="end"
              fontSize="9"
              fill="var(--color-deep-navy)"
              transform={`rotate(-40 ${paddingX + years.length * step} ${chartHeight})`}
            >
              {forecastYear}
            </text>
          )}
        </svg>
      </div>
      {hasUnreliableYears && (
        <p className={styles.patentNote}>* 잠정치·공개지연으로 예측 학습에서 제외된 연도예요</p>
      )}
      <p className={styles.emptyText}>검색 키워드(AI 자동생성): {data.keyword}</p>
    </div>
  );
}

function DensityGridView({ grid }: { grid: DensityGrid }) {
  const cols = grid.grid_cols || DENSITY_GRID_COLS;
  const rows = grid.grid_rows || DENSITY_GRID_ROWS;
  const cellMap = new Map<string, DensityCell>();
  grid.cells.forEach((cell) => cellMap.set(`${cell.x},${cell.y}`, cell));
  const maxCount = Math.max(0, ...grid.cells.map((c) => c.count));

  const items: Array<DensityCell | null> = [];
  for (let y = 0; y < rows; y += 1) {
    for (let x = 0; x < cols; x += 1) {
      items.push(cellMap.get(`${x},${y}`) ?? null);
    }
  }

  return (
    <div className={styles.densityWrap}>
      <div className={styles.densityGrid} style={{ gridTemplateColumns: `repeat(${cols}, 1fr)`, gridTemplateRows: `repeat(${rows}, 1fr)` }}>
        {items.map((cell, index) => {
          const color = getDensityColor(cell?.count ?? null, maxCount);
          const ratio = cell && maxCount > 0 ? cell.count / maxCount : 0;
          return (
            <div key={index} className={styles.densityCell} style={{ background: color, color: ratio > 0.5 ? "var(--color-white)" : "var(--color-ink-charcoal)" }}>
              {cell && (
                <>
                  <span className={styles.densityCount}>{cell.count}</span>
                  <span className={styles.densitySigungu}>{cell.sigungu}</span>
                </>
              )}
            </div>
          );
        })}
      </div>
      <p className={styles.emptyText}>
        * 진한 색일수록 동종업종 벤처기업 밀집 · 상위 {grid.shown_sigungu_count}개 지역 기준 (전체 {grid.total_sigungu_count}개 중)
      </p>
    </div>
  );
}

export default DiagnosisTechReport;
